"""The upload page: sorting, duplicates, the PDF chain, rules-only fallback and documents (fictional files only)."""
import http.client
import io
import json
import socket
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from app import server
from app.auth import Auth
from app.server import Service
from app.uploads import looks_like_drawing, sort_file

ROOT = Path(__file__).resolve().parents[1]
BY = "Test Inspector (fictitious)"


def jpeg(colour="red") -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (64, 48), colour).save(b, "JPEG")
    return b.getvalue()


def png() -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(b, "PNG")
    return b.getvalue()


def pdf_without_table(text="General arrangement, deck 2 (fictitious)") -> bytes:
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(72, 720, text)
    c.save()
    return b.getvalue()


class Sorting(unittest.TestCase):
    def test_drawing_names_whole_words_and_ga_at_the_start(self):
        for name in ("GA-02 deck.png", "ga_03.png", "GA 1.pdf", "deck plan.png", "deck_plan.png", "Layout engine room.jpg",
                     "tekeningen dek 2.pdf", "PLANS.PDF", "drawing 4.png"):
            with self.subTest(name=name):
                self.assertTrue(looks_like_drawing(name))
        for name in ("GA02.png", "Gallery.jpg", "plank.jpg", "floorplan.png", "MM-1 F-012.jpg", "overview.jpg", "tag GA-1.png"):
            with self.subTest(name=name):
                self.assertFalse(looks_like_drawing(name))

    def test_sorted_by_content_then_name(self):
        self.assertEqual(sort_file("MM-1.jpg", jpeg()), "photo")
        self.assertEqual(sort_file("GA-02 deck.png", png()), "drawing")
        self.assertEqual(sort_file("lab.pdf", b"%PDF-1.4 ..."), "pdf")
        self.assertEqual(sort_file("GA-03.pdf", b"%PDF-1.4 ..."), "drawing")
        self.assertEqual(sort_file("notes.jpg", b"just text"), "unknown")        # the name alone never decides
        self.assertEqual(sort_file("iphone.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 20), "photo")


class UploadFlow(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.s = Service(":memory:", data_dir=self.dir)
        self.oid = self.s.demo_object

    def up(self, name, data):
        return self.s.upload_file(self.oid, name, data, BY)

    def test_lab_pdf_goes_through_the_chain_with_counts(self):
        out = self.up("dev5_lab.pdf", (ROOT / "dev5_lab.pdf").read_bytes())
        self.assertEqual(out["kind"], "lab")
        self.assertEqual(out["lines"], out["by_rules"] + out["by_ai"] + out["needs_you"])
        self.assertGreater(out["lines"], 0)
        rep = self.s.view(out["report"], self.oid)["report"]
        self.assertEqual(rep["evidence"]["source_file"], "dev5_lab.pdf")

    def test_same_file_twice_is_skipped_for_every_kind(self):
        lab = (ROOT / "dev4_lab.pdf").read_bytes()
        self.assertEqual(self.up("dev4_lab.pdf", lab)["kind"], "lab")
        self.assertEqual(self.up("copy of dev4.pdf", lab)["kind"], "skipped")         # by file hash, not name
        self.assertTrue(self.up("MM-2 extra.jpg", jpeg("green")).get("id"))
        self.assertTrue(self.up("again.jpg", jpeg("green"))["skipped"])
        self.assertEqual(self.up("GA-02 deck.png", png())["kind"], "drawing")
        self.assertEqual(self.up("GA-02 copy.png", png())["kind"], "skipped")
        self.assertEqual(len(self.s.view(None, self.oid)["reports"]), 2)               # the demo report + dev4 once

    def test_pdf_without_results_table_asks_once_and_files_the_answer(self):
        data = pdf_without_table()
        out = self.up("scan 7.pdf", data)
        self.assertEqual(out["kind"], "ask")
        self.assertEqual(self.up("scan 7 again.pdf", data)["kind"], "skipped")
        self.s.decide_file(self.oid, out["id"], "drawing", BY)
        doc = self.s.view(None, self.oid)["documents"][0]
        self.assertEqual((doc["kind"], doc["status"]), ("ga_drawing", "filed"))
        other = self.up("scan 8.pdf", pdf_without_table("Something else (fictitious)"))
        self.assertIn("paste the lines", self.s.decide_file(self.oid, other["id"], "lab", BY).lower())
        self.assertEqual(self.s.store.document(other["id"])["status"], "unreadable_lab")
        with self.assertRaises(ValueError):
            self.s.decide_file(self.oid, other["id"], "drawing", BY)                    # answered already

    def test_a_drawing_pdf_is_filed_without_reading_it(self):
        out = self.up("GA-01 general arrangement.pdf", pdf_without_table())
        self.assertEqual(out["kind"], "drawing")
        self.assertTrue((Path(self.dir) / "docs" / str(self.oid)).is_dir())

    def test_rules_only_when_the_ai_service_is_down(self):
        class Down:
            def complete(self, text):
                raise ConnectionError("no route to the AI service")
        self.s.client = Down()
        out = self.up("dev5_lab.pdf", (ROOT / "dev5_lab.pdf").read_bytes())
        self.assertEqual((out["kind"], out["ai"], out["by_ai"]), ("lab", "unavailable", 0))
        self.assertEqual(out["lines"], out["by_rules"] + out["needs_you"])

    def test_wrong_guesses_move_with_one_click(self):
        photo = self.up("MM-2 extra.jpg", jpeg("teal"))
        self.s.move_file(self.oid, "photo", photo["id"], BY)
        self.assertIsNone(self.s.store.photo(photo["id"]))
        doc = self.s.view(None, self.oid)["documents"][-1]
        self.assertEqual((doc["kind"], doc["name"]), ("ga_drawing", "MM-2 extra.jpg"))
        self.s.move_file(self.oid, "document", doc["id"], BY)
        self.assertEqual(self.s.view(None, self.oid)["documents"], [])
        actions = [e["action"] for e in self.s.store.register_log(self.oid)]
        self.assertIn("photo moved", actions)
        self.assertIn("document moved", actions)

    def test_moving_a_registered_photo_number_keeps_the_number(self):
        out = self.up("MM-1 F-012 pipe.jpg", jpeg("navy"))                 # fills the registered F-012 of MM-1
        self.s.move_file(self.oid, "photo", out["id"], BY)
        row = self.s.store.photo(out["id"])
        self.assertEqual((row["photo_no"], row["sample_code"], row["stored_name"]), ("F-012", "MM-1", None))
        self.assertEqual(self.s.view(None, self.oid)["documents"][-1]["name"], "MM-1 F-012 pipe.jpg")

    def test_other_file_types_are_refused(self):
        with self.assertRaisesRegex(ValueError, "cannot read this file type"):
            self.up("notes.docx", b"PK\x03\x04 not a pdf")

    def test_demo_pdfs_and_photos_in_one_go(self):
        from app.demo.make_demo_photos import make
        files = [ROOT / "dev4_lab.pdf", ROOT / "dev5_lab.pdf"] + make(Path(tempfile.mkdtemp()))
        results = [self.up(f.name, f.read_bytes()) for f in files]
        kinds = [r["kind"] for r in results]
        self.assertEqual(kinds.count("lab"), 2)
        self.assertEqual(kinds.count("photo"), 19)
        self.assertGreaterEqual(sum(1 for r in results if r["kind"] == "photo" and r.get("linked")), 15)


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ready = threading.Event()

        def run():
            server.AUTH = Auth({})
            server.SERVICE = Service(":memory:", data_dir=cls.dir)
            cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            cls.httpd.daemon_threads = True
            cls.port = cls.httpd.server_address[1]
            ready.set()
            cls.httpd.serve_forever()

        threading.Thread(target=run, daemon=True).start()
        ready.wait(10)
        cls.ship = server.SERVICE.demo_object
        cls.other = server.SERVICE.new_project({"name": "MV Other (fictitious)", "site": "Yard", "project": "J-26-950"})

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body, headers or {})
        res = conn.getresponse()
        out = (res.status, dict(res.getheaders()), res.read())
        conn.close()
        return out

    def test_upload_and_open_a_drawing_only_in_its_own_project(self):
        status, _, body = self.call("POST", f"/api/file?object={self.ship}&name=GA-02%20deck.png", png(),
                                    {"X-Inspector": "Test%20Inspector"})
        self.assertEqual(status, 200, body)
        did = json.loads(body)["id"]
        ok = self.call("GET", f"/api/document/{did}?object={self.ship}")
        self.assertEqual((ok[0], ok[1]["Content-Type"]), (200, "image/png"))
        self.assertEqual(self.call("GET", f"/api/document/{did}?object={self.other}")[0], 404)

    def test_pdf_limit_is_20_mb_before_reading(self):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        s.sendall((f"POST /api/file?object={self.ship}&name=big.pdf HTTP/1.1\r\nHost: x\r\n"
                   f"Content-Length: {21 * 1024 * 1024}\r\n\r\n").encode())
        answer = s.recv(4096)
        s.close()
        self.assertIn(b" 413 ", answer.split(b"\r\n")[0])


if __name__ == "__main__":
    unittest.main()
