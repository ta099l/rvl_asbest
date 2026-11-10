"""Tests for the optional login (fictitious data only)."""
import http.client
import json
import threading
import unittest
from http.server import HTTPServer

from app import server
from app.auth import MAX_FAILURES, Auth, parse_users


class ParseUsersTests(unittest.TestCase):
    def test_reads_names_and_passwords(self):
        self.assertEqual(parse_users("Ivan Hoornweg:pw1; Tasnim:pw2"), {"Ivan Hoornweg": "pw1", "Tasnim": "pw2"})

    def test_empty_means_no_login(self):
        self.assertEqual(parse_users(None), {})
        self.assertFalse(Auth(parse_users("")).enabled)

    def test_bad_format_is_refused(self):
        for bad in ("Ivan", "Ivan:", ":pw"):
            with self.assertRaises(ValueError):
                parse_users(bad)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.a = Auth({"Ivan": "pw1", "Tasnim": "pw2"}, secret="s3cret", clock=lambda: self.now)

    def test_right_and_wrong_password(self):
        self.assertEqual(self.a.check("ivan", "pw1"), "Ivan")      # name is not case sensitive
        self.assertIsNone(self.a.check("Ivan", "pw2"))
        self.assertIsNone(self.a.check("Nobody", "pw1"))

    def test_token_round_trip_and_tampering(self):
        token = self.a.make_token("Ivan")
        self.assertEqual(self.a.read_token(token), "Ivan")
        enc, expiry, sig = token.split(".")
        other = Auth({"Ivan": "pw1"}, secret="other", clock=lambda: self.now)
        self.assertIsNone(other.read_token(token))                  # signed with another secret
        self.assertIsNone(self.a.read_token(f"{enc}.{int(expiry) + 99999}.{sig}"))   # expiry changed
        self.assertIsNone(self.a.read_token("garbage"))
        self.assertIsNone(self.a.read_token(None))

    def test_token_expires(self):
        token = self.a.make_token("Ivan")
        self.now += 13 * 3600
        self.assertIsNone(self.a.read_token(token))

    def test_guessing_is_slowed_down(self):
        for _ in range(MAX_FAILURES):
            self.assertIsNone(self.a.check("Ivan", "wrong", "1.2.3.4"))
        self.assertTrue(self.a.blocked("1.2.3.4"))
        self.assertIsNone(self.a.check("Ivan", "pw1", "1.2.3.4"))   # even the right password waits
        self.assertEqual(self.a.check("Ivan", "pw1", "5.6.7.8"), "Ivan")   # other address is fine
        self.now += 61
        self.assertEqual(self.a.check("Ivan", "pw1", "1.2.3.4"), "Ivan")

    def test_cookie_header(self):
        token = self.a.make_token("Tasnim")
        self.assertEqual(self.a.user_from_cookie_header(f"x=1; james_session={token}; y=2"), "Tasnim")
        self.assertIsNone(self.a.user_from_cookie_header("x=1"))


class ServerLoginTests(unittest.TestCase):
    """A real server on a free port, started in its own thread (SQLite wants one thread)."""

    @classmethod
    def setUpClass(cls):
        ready = threading.Event()

        def run():
            server.AUTH = Auth({"Ivan": "pw1", "Tasnim": "pw2"}, secret="s3cret")
            server.SERVICE = server.Service(":memory:")
            cls.httpd = HTTPServer(("127.0.0.1", 0), server.Handler)
            cls.port = cls.httpd.server_address[1]
            ready.set()
            cls.httpd.serve_forever()

        cls.thread = threading.Thread(target=run, daemon=True)
        cls.thread.start()
        ready.wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.AUTH = Auth({})

    def call(self, method, path, body=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        res = conn.getresponse()
        data = res.read()
        out = (res.status, dict(res.getheaders()), data)
        conn.close()
        return out

    def login(self, name="Ivan", password="pw1"):
        status, headers, _ = self.call("POST", "/api/login", {"name": name, "password": password})
        return status, (headers.get("Set-Cookie") or "").split(";")[0]

    def test_everything_needs_a_login(self):
        status, headers, _ = self.call("GET", "/")
        self.assertEqual((status, headers["Location"]), (302, "/login"))
        self.assertEqual(self.call("GET", "/api/state")[0], 401)
        self.assertEqual(self.call("POST", "/api/reset", {})[0], 401)
        self.assertEqual(self.call("GET", "/login")[0], 200)
        self.assertEqual(self.call("GET", "/healthz")[0], 200)

    def test_wrong_password_gets_no_cookie(self):
        status, cookie = self.login("Ivan", "nope")
        self.assertEqual((status, cookie), (401, ""))

    def test_logged_in_user_sees_the_app_and_signs_with_their_own_name(self):
        status, cookie = self.login("Tasnim", "pw2")
        self.assertEqual(status, 200)
        self.assertEqual(self.call("GET", "/", cookie=cookie)[0], 200)
        state = json.loads(self.call("GET", "/api/state", cookie=cookie)[2])
        self.assertEqual((state["me"], state["login"]), ("Tasnim", True))
        # the browser tries to sign as someone else: the server ignores that
        self.call("POST", "/api/demo", {"which": "b1"}, cookie=cookie)
        rid = json.loads(self.call("GET", "/api/state", cookie=cookie)[2])["report"]["id"]
        out = json.loads(self.call("POST", "/api/decide", {"report_id": rid, "idx": 0, "action": "approve",
                                                           "by": "Mallory"}, cookie=cookie)[2])
        self.assertEqual(out["report"]["rows"][0]["decision"]["by"], "Tasnim")

    def test_a_forged_cookie_is_refused(self):
        self.assertEqual(self.call("GET", "/api/state", cookie="james_session=abc.123.def")[0], 401)

    def test_logout_clears_the_cookie(self):
        _, cookie = self.login()
        status, headers, _ = self.call("POST", "/api/logout", {}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])


if __name__ == "__main__":
    unittest.main()
