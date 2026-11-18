"""Photos: checks, storage, numbering, proposals and the HTTP routes (fictional images only)."""
import http.client
import io
import json
import socket
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from app import photos, server
from app.auth import Auth
from app.photos import PhotoError, check_image, next_photo_no, process, propose
from app.server import Service

BY = "Test Inspector (fictitious)"


def jpeg(colour="red", size=(64, 48), **save) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", size, colour).save(b, "JPEG", **save)
    return b.getvalue()


def png(colour="blue") -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", (40, 30), colour).save(b, "PNG")
    return b.getvalue()


class Checks(unittest.TestCase):
    def test_magic_bytes(self):
        self.assertEqual(check_image(jpeg()), "jpeg")
        self.assertEqual(check_image(png()), "png")
        with self.assertRaisesRegex(PhotoError, "export it as JPG"):
            check_image(b"this is a text file renamed to photo.jpg")
        with self.assertRaisesRegex(PhotoError, "HEIC"):
            check_image(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 40)

    def test_a_broken_file_with_a_jpeg_start_is_refused(self):
        with self.assertRaises(PhotoError):
            process(b"\xff\xd8\xff" + b"not really a photo" * 20)

    def test_upright_and_without_exif(self):
        exif = Image.Exif()
        exif[0x0112] = 6                                 # phone held upright: "rotate 90 to view"
        sideways = jpeg(size=(48, 64), exif=exif)
        full, thumb, w, h = process(sideways)
        self.assertEqual((w, h), (64, 48))               # turned upright
        out = Image.open(io.BytesIO(full))
        self.assertEqual(len(out.getexif()), 0)          # no EXIF at all, so no GPS position either
        self.assertEqual(out.format, "JPEG")
        self.assertLessEqual(max(Image.open(io.BytesIO(thumb)).size), photos.THUMB_PX)

    def test_png_becomes_jpeg(self):
        full, _, w, h = process(png())
        self.assertEqual((Image.open(io.BytesIO(full)).format, w, h), ("JPEG", 40, 30))


class Numbering(unittest.TestCase):
    def test_continues_the_projects_format(self):
        self.assertEqual(next_photo_no(["F-012", "F-007"]), "F-013")
        self.assertEqual(next_photo_no(["P01", "P02"]), "P03")
        self.assertEqual(next_photo_no(["7", "3"]), "8")
        self.assertEqual(next_photo_no([]), "1")
        self.assertEqual(next_photo_no(["overview"]), "1")


class Proposals(unittest.TestCase):
    SAMPLES = {"MM-1": "B01", "PBS-3": "B05", "HM-12": "B08", "CR6-2": ""}
    SOURCES = ["B01", "B04", "B05", "B08"]

    def test_a_sample_code_in_the_file_name(self):
        for name, code in (("M01.jpg", "MM-1"), ("mm-1 pipe.jpg", "MM-1"), ("PBS-03.jpg", "PBS-3"), ("pbs 3.png", "PBS-3"),
                           ("hm12_2.jpg", "HM-12"), ("HM-12 railing.jpeg", "HM-12"), ("cr602.jpg", "CR6-2")):
            with self.subTest(name=name):
                self.assertEqual(propose(name, self.SAMPLES, self.SOURCES)[0], code)
        self.assertEqual(propose("M01.jpg", self.SAMPLES, self.SOURCES)[1], "B01")     # and its source

    def test_a_source_code_in_the_file_name(self):
        self.assertEqual(propose("B4 overview.jpg", self.SAMPLES, self.SOURCES)[:2], (None, "B04"))

    def test_no_proposal(self):
        for name in ("overview.jpg", "IMG_2041.jpg", "MI02.jpg", "M12.jpg", "HM1.jpg", "B9.jpg"):
            with self.subTest(name=name):
                self.assertEqual(propose(name, self.SAMPLES, self.SOURCES)[:2], (None, None))

    def test_two_samples_in_one_name_is_not_guessed(self):
        sample, source, reason = propose("MM-1 HM-12.jpg", self.SAMPLES, self.SOURCES)
        self.assertEqual((sample, source), (None, None))
        self.assertIn("more than one sample", reason)


class UploadInTheService(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.s = Service(":memory:", data_dir=self.dir)
        self.oid = self.s.demo_object

    def test_stored_under_the_data_folder_by_sha256(self):
        data = jpeg("green")
        out = self.s.upload_photo(self.oid, "MM-2 extra.jpg", data, BY)
        row = self.s.store.photo(out["id"])
        self.assertEqual(row["stored_name"], photos.sha256(data))
        self.assertTrue((Path(self.dir) / "photos" / str(self.oid) / f"{row['stored_name']}.jpg").is_file())
        self.assertTrue((Path(self.dir) / "photos" / str(self.oid) / "thumbs" / f"{row['stored_name']}.jpg").is_file())
        self.assertEqual((row["original_name"], row["proposed_sample"]), ("MM-2 extra.jpg", "MM-2"))
        self.assertEqual(out["photo_no"], "F-058")       # continues the demo ship's F-057

    def test_duplicate_is_skipped(self):
        data = jpeg("yellow")
        self.s.upload_photo(self.oid, "a.jpg", data, BY)
        out = self.s.upload_photo(self.oid, "same photo again.jpg", data, BY)
        self.assertTrue(out["skipped"])
        self.assertIn("already here", out["message"])
        self.assertEqual(sum(1 for r in self.s.store.photos(self.oid) if r["stored_name"]), 1)

    def test_a_registered_photo_number_gets_its_file(self):
        before = len(self.s.store.photos(self.oid))
        out = self.s.upload_photo(self.oid, "MM-1 F-012 pipe.jpg", jpeg("navy"), BY)
        self.assertEqual(out["photo_no"], "F-012")
        self.assertEqual(len(self.s.store.photos(self.oid)), before)      # no duplicate row
        self.assertEqual(self.s.store.photo(out["id"])["sample_code"], "MM-1")

    def test_text_file_is_refused_and_nothing_is_stored(self):
        with self.assertRaises(ValueError):
            self.s.upload_photo(self.oid, "notes.jpg", b"just text, renamed to .jpg", BY)
        self.assertFalse((Path(self.dir) / "photos").exists())

    def test_upload_is_signed(self):
        with self.assertRaises(ValueError):
            self.s.upload_photo(self.oid, "a.jpg", jpeg(), "")

    def test_the_demo_photos_link_at_least_15_automatically(self):
        from app.demo.make_demo_photos import make
        files = make(Path(tempfile.mkdtemp()))
        linked = sum(bool(self.s.upload_photo(self.oid, f.name, f.read_bytes(), BY).get("linked")) for f in files)
        self.assertGreaterEqual(linked, 15)
        self.assertEqual(self.s.accept_photo_proposals(self.oid, BY), 9)
        rotated = next(r for r in self.s.store.photos(self.oid) if r["photo_no"] == "F-024")
        self.assertEqual((rotated["width"], rotated["height"]), (1600, 1200))   # EXIF rotation applied

    def test_link_fills_the_description_and_accept_all(self):
        out = self.s.upload_photo(self.oid, "PBS-2 window.jpg", jpeg("teal"), BY)
        self.assertEqual(self.s.accept_photo_proposals(self.oid, BY), 1)
        row = self.s.store.photo(out["id"])
        self.assertEqual((row["sample_code"], row["source_no"]), ("PBS-2", "B09"))
        self.assertEqual(row["description"], "Bridge, window - Window rubber, Window")

    def test_photo_number_stays_unique(self):
        out = self.s.upload_photo(self.oid, "x.jpg", jpeg("olive"), BY)
        with self.assertRaisesRegex(ValueError, "already used"):
            self.s.update_photo(self.oid, out["id"], {"photo_no": "F-012"}, BY)


class OverHttp(unittest.TestCase):
    """The real server with login on, in its own thread."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ready = threading.Event()

        def run():
            server.AUTH = Auth({"Tasnim": "pw"}, secret="s3cret")
            server.SERVICE = Service(":memory:", data_dir=cls.dir)
            cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            cls.httpd.daemon_threads = True
            cls.port = cls.httpd.server_address[1]
            ready.set()
            cls.httpd.serve_forever()

        threading.Thread(target=run, daemon=True).start()
        ready.wait(10)
        cls.ship = server.SERVICE.demo_object
        cls.other = server.SERVICE.new_project({"name": "MV Other (fictitious)", "site": "Yard", "project": "J-26-700"})
        status, headers, _ = cls.call("POST", "/api/login", json.dumps({"name": "Tasnim", "password": "pw"}).encode())
        cls.cookie = headers["Set-Cookie"].split(";")[0]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.AUTH = Auth({})

    @classmethod
    def call(cls, method, path, body=None, cookie=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        h = dict(headers or {})
        if cookie:
            h["Cookie"] = cookie
        conn.request(method, path, body, h)
        res = conn.getresponse()
        out = (res.status, dict(res.getheaders()), res.read())
        conn.close()
        return out

    def upload(self, data, name="MM-3 flange.jpg", obj=None):
        return self.call("POST", f"/api/photo?object={obj or self.ship}&name={name.replace(' ', '%20')}", data, self.cookie)

    def test_upload_and_serve_only_for_its_own_project(self):
        status, _, body = self.upload(jpeg("purple"))
        self.assertEqual(status, 200, body)
        pid = json.loads(body)["id"]
        ok = self.call("GET", f"/api/photo/{pid}/thumb?object={self.ship}", cookie=self.cookie)
        self.assertEqual((ok[0], ok[1]["Content-Type"]), (200, "image/jpeg"))
        self.assertEqual(self.call("GET", f"/api/photo/{pid}?object={self.ship}", cookie=self.cookie)[0], 200)
        self.assertEqual(self.call("GET", f"/api/photo/{pid}?object={self.other}", cookie=self.cookie)[0], 404)  # wrong project
        self.assertEqual(self.call("GET", f"/api/photo/{pid}", cookie=self.cookie)[0], 404)                      # no project named
        self.assertEqual(self.call("GET", f"/api/photo/{pid}?object={self.ship}")[0], 401)                       # not logged in

    def test_upload_needs_a_login(self):
        self.assertEqual(self.call("POST", f"/api/photo?object={self.ship}&name=a.jpg", jpeg())[0], 401)

    def test_text_renamed_to_jpg_is_refused(self):
        status, _, body = self.upload(b"hello, this is text", "notes.jpg")
        self.assertEqual(status, 400)
        self.assertIn("export it as JPG", json.loads(body)["error"])

    def raw(self, request: bytes, body_part: bytes = b"") -> bytes:
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        s.sendall(request + body_part)
        data = s.recv(4096)
        s.close()
        return data

    def test_too_large_is_refused_before_reading(self):
        # announces 40 MB but sends nothing: the answer must come at once, without waiting for the body
        start = time.monotonic()
        head = (f"POST /api/photo?object={self.ship}&name=big.jpg HTTP/1.1\r\nHost: x\r\nCookie: {self.cookie}\r\n"
                f"Content-Length: {40 * 1024 * 1024}\r\n\r\n").encode()
        answer = self.raw(head)
        self.assertIn(b" 413 ", answer.split(b"\r\n")[0])
        self.assertLess(time.monotonic() - start, 3)
        head = (f"POST /api/sample HTTP/1.1\r\nHost: x\r\nCookie: {self.cookie}\r\nContent-Length: {26 * 1024 * 1024}\r\n\r\n").encode()
        self.assertIn(b" 413 ", self.raw(head).split(b"\r\n")[0])           # JSON: 25 MB

    def test_missing_content_length_is_refused(self):
        head = f"POST /api/sample HTTP/1.1\r\nHost: x\r\nCookie: {self.cookie}\r\n\r\n".encode()
        self.assertIn(b" 411 ", self.raw(head).split(b"\r\n")[0])

    def test_a_slow_upload_does_not_block_other_windows(self):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        s.sendall((f"POST /api/photo?object={self.ship}&name=slow.jpg HTTP/1.1\r\nHost: x\r\nCookie: {self.cookie}\r\n"
                   f"Content-Length: {5 * 1024 * 1024}\r\n\r\n").encode() + b"\xff\xd8\xff" + b"\x00" * 1000)   # stalls here
        try:
            start = time.monotonic()
            status = self.call("GET", f"/api/state?object={self.ship}", cookie=self.cookie)[0]
            self.assertEqual(status, 200)
            self.assertLess(time.monotonic() - start, 3)
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
