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
<meta name="color-scheme" content="light dark"><title>James · Log in</title>
<style>
  :root{--font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;--bg:#f6f7f5;--surface:#fff;
    --border:#e3e6e1;--border-strong:#cdd2cb;--text:#18201b;--text-2:#56605a;--text-3:#848c86;--brand:#1f5a43;--brand-hover:#174835;
    --on-brand:#fff;--bad:#b2321d;--warn:#8f5c00;--warn-soft:#fbf1d9}
  @media (prefers-color-scheme:dark){:root{--bg:#101211;--surface:#171a18;--border:#282d2a;--border-strong:#39403b;--text:#e7ebe8;
    --text-2:#a2aaa5;--text-3:#78807b;--brand:#53b38a;--brand-hover:#66c49b;--on-brand:#07130d;--bad:#f0806b;--warn:#e0a842;--warn-soft:#33291a}}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px;background:var(--bg);color:var(--text);font:14px/1.5 var(--font)}
  main{width:min(380px,100%);background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:32px}
  .brand{display:flex;align-items:center;gap:8px;font-weight:600;font-size:16px;margin-bottom:24px}
  .mark{width:28px;height:28px;border-radius:6px;background:var(--brand);color:var(--on-brand);display:grid;place-items:center;font-weight:700}
  h1{font-size:20px;font-weight:600;margin:0 0 4px}
  p{color:var(--text-2);margin:0 0 20px;font-size:13px}
  label{display:grid;gap:4px;font-size:13px;font-weight:500;color:var(--text-2);margin-top:14px}
  input{width:100%;height:36px;padding:6px 10px;border:1px solid var(--border-strong);border-radius:6px;font:inherit;color:var(--text);background:var(--surface)}
  input:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 3px color-mix(in srgb,var(--brand) 30%,transparent)}
  button{margin-top:20px;width:100%;height:36px;border:1px solid var(--brand);border-radius:6px;background:var(--brand);color:var(--on-brand);font:500 14px var(--font);cursor:pointer}
  button:hover{background:var(--brand-hover)}
  button:focus-visible{outline:none;box-shadow:0 0 0 3px color-mix(in srgb,var(--brand) 30%,transparent)}
  button:disabled{opacity:.6;cursor:wait}
  .note{margin-top:20px;font-size:12px;color:var(--text-2);border-left:3px solid var(--warn);background:var(--warn-soft);border-radius:6px;padding:8px 10px}
  #err{color:var(--bad);margin-top:10px;min-height:1.2em;font-size:13px}
</style></head><body><main>
<div class="brand"><span class="mark" aria-hidden="true">J</span>James</div>
<h1>Log in</h1><p>Lab agent prototype. Use the name and password you got from the team.</p>
<form id="f"><label>Name<input id="n" autocomplete="username" autofocus required></label>
<label>Password<input id="p" type="password" autocomplete="current-password" required></label>
<button id="b">Log in</button><div id="err" role="alert"></div></form>
<div class="note">Concept prototype. Fictitious data only: do not upload real RVL documents here.</div>
</main><script>
document.getElementById("f").onsubmit = async (e) => {
  e.preventDefault();
  const b = document.getElementById("b"); b.disabled = true; b.textContent = "Logging in…";
  try {
    const res = await fetch("/api/login", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({name: document.getElementById("n").value, password: document.getElementById("p").value})});
    if (res.ok) { location.href = "/"; return; }
    const d = await res.json().catch(() => ({}));
    document.getElementById("err").textContent = d.error || "Log in failed.";
  } catch (err) {
    document.getElementById("err").textContent = "The server could not be reached.";
  }
  b.disabled = false; b.textContent = "Log in";
};
</script></body></html>
"""
