"""Optional login for a shared copy of the app (hosted, or on a network).

Off by default: running on your own laptop needs no login. It switches on when
the environment variable JAMES_USERS is set, for example

    JAMES_USERS="Ivan Hoornweg:password1;Tasnim:password2"

(name and password separated by a colon, people separated by a semicolon; the
password itself may not contain ':' or ';'). Passwords live only in the
environment of the server, never in the repository.

Rules:
- Every page and every API call needs a login, except the login page itself.
- The name that signs a decision is always the logged-in name. The browser can
  not choose another one.
- After 5 wrong passwords from one address within a minute, that address waits.
- The session cookie is signed (HMAC) and expires after 12 hours.
"""
import base64
import hashlib
import hmac
import secrets
import time
from typing import Dict, List, Optional

SESSION_SECONDS = 12 * 3600
MAX_FAILURES = 5
WINDOW_SECONDS = 60
COOKIE = "james_session"


def parse_users(spec: Optional[str]) -> Dict[str, str]:
    users: Dict[str, str] = {}
    for part in (spec or "").split(";"):
        part = part.strip()
        if not part:
            continue
        name, sep, password = part.partition(":")
        name, password = name.strip(), password.strip()
        if not sep or not name or not password:
            raise ValueError("JAMES_USERS must look like: Name:password;Other Name:password2")
        users[name] = password
    return users


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _unb64(text: str) -> str:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode("utf-8")


class Auth:
    def __init__(self, users: Dict[str, str], secret: Optional[str] = None, clock=time.time):
        self.users = dict(users)
        self.secret = (secret or secrets.token_hex(32)).encode("utf-8")
        self.clock = clock
        self.failures: Dict[str, List[float]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.users)

    # --- password check, with a limit on guessing -----------------------------------
    def blocked(self, address: str) -> bool:
        now = self.clock()
        recent = [t for t in self.failures.get(address, []) if now - t < WINDOW_SECONDS]
        self.failures[address] = recent
        return len(recent) >= MAX_FAILURES

    def check(self, name: str, password: str, address: str = "") -> Optional[str]:
        """Return the account name when name and password are right, else None."""
        if self.blocked(address):
            return None
        found = None
        for known, pw in self.users.items():                 # compare with all: same time for every try
            ok_name = hmac.compare_digest(known.lower().encode(), (name or "").strip().lower().encode())
            ok_pw = hmac.compare_digest(pw.encode(), (password or "").encode())
            if ok_name and ok_pw:
                found = known
        if found is None:
            self.failures.setdefault(address, []).append(self.clock())
        return found

    # --- session cookie ----------------------------------------------------------------
    def _sign(self, payload: str) -> str:
        return hmac.new(self.secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def make_token(self, name: str) -> str:
        payload = f"{_b64(name)}.{int(self.clock()) + SESSION_SECONDS}"
        return f"{payload}.{self._sign(payload)}"

    def read_token(self, token: Optional[str]) -> Optional[str]:
        try:
            enc, expiry, sig = (token or "").split(".")
            if not hmac.compare_digest(self._sign(f"{enc}.{expiry}"), sig):
                return None
            if int(expiry) < self.clock():
                return None
            name = _unb64(enc)
        except (ValueError, UnicodeDecodeError):
            return None
        return name if name in self.users else None

    def user_from_cookie_header(self, header: Optional[str]) -> Optional[str]:
        for part in (header or "").split(";"):
            key, _, value = part.strip().partition("=")
            if key == COOKIE:
                return self.read_token(value)
        return None


LOGIN_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>James · Log in</title>
<style>
  body{margin:0;background:#f3f4f0;color:#1b2a22;font:15px/1.5 "Segoe UI",system-ui,Arial,sans-serif;display:grid;place-items:center;min-height:100vh}
  main{background:#fff;border:1px solid #dde2da;border-radius:12px;padding:28px;width:min(380px,92vw)}
  h1{font:600 26px Georgia,serif;color:#1f3d2e;margin:0 0 4px}
  p{color:#5f6b64;margin:0 0 16px;font-size:14px}
  label{display:block;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#5f6b64;margin-top:12px}
  input{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #dde2da;border-radius:6px;font:inherit;margin-top:4px}
  button{margin-top:18px;width:100%;padding:10px;border:0;border-radius:8px;background:#1f3d2e;color:#fff;font:inherit;cursor:pointer}
  .note{margin-top:14px;font-size:12.5px;color:#7a3a0c;background:#fbeee3;border-radius:8px;padding:8px 10px}
  #err{color:#a8321c;margin-top:10px;min-height:1.2em;font-size:14px}
</style></head><body><main>
<h1>James</h1><p>Lab agent prototype. Log in with the name and password you got from the team.</p>
<form id="f"><label>Name<input id="n" autocomplete="username" autofocus></label>
<label>Password<input id="p" type="password" autocomplete="current-password"></label>
<button>Log in</button><div id="err"></div></form>
<div class="note">Concept prototype. Fictitious data only: do not upload real RVL documents here.</div>
</main><script>
document.getElementById("f").onsubmit = async (e) => {
  e.preventDefault();
  const res = await fetch("/api/login", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name: document.getElementById("n").value, password: document.getElementById("p").value})});
  if (res.ok) { location.href = "/"; return; }
  const d = await res.json().catch(() => ({}));
  document.getElementById("err").textContent = d.error || "Log in failed.";
};
</script></body></html>
"""
