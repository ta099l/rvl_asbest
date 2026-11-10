"""Build the demo artifact from the real app screen, so the two always look the same.

    python app/demo/build_artifact.py

Takes app/static/index.html as it is, takes the demo ship and the linker's proposals from
the real Python app (Service), and adds mock_api.js, which answers the screen's API calls
inside the browser. Writes app/demo/james-lab-agent.html. Run it again after any change
to the app screen, then publish that file.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.demo_data import SHIP          # noqa: E402
from app.server import Service           # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "james-lab-agent.html"
KEEP = ("n", "idx", "raw_line", "raw_id", "description", "result", "method", "certificate", "quantity", "remarks",
        "findings", "proposal")


def snapshot(s: Service, rid: int) -> dict:
    """What the browser needs of one report: the rows with the linker's proposals, nothing decided yet."""
    r = s.view(rid)["report"]
    rules = {row["idx"]: row["proposed_code"] for row in s.store.rows(rid)}
    return {"label": r["label"], "ref": r["ref"], "lab": r["lab"], "ai_note": r["ai_note"], "evidence": r["evidence"],
            "rows": [{**{k: x[k] for k in KEEP}, "rules_code": rules[x["idx"]]} for x in r["rows"]],
            "agent": [e["text"] for e in s.agent_log if e["report_id"] == rid]}


def demo_data() -> dict:
    s = Service()
    v = s.view(None)
    o = v["object"]
    data = {"object": {k: o[k] for k in ("name", "kind", "ref", "site", "project", "survey_date")},
            "info": SHIP.get("info", {}),
            "register": [{k: x[k] for k in x if k != "missing"} for x in v["register"]],
            "reports": {"b1": snapshot(s, v["report"]["id"])}}
    data["reports"]["b2"] = snapshot(s, s.load_demo("b2"))
    pid = s.load_practice()
    data["practice"] = {**snapshot(s, pid), "seeded": {str(k): w for k, w in s.practice[pid].items()}}
    return data


def build() -> Path:
    page = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    style = re.search(r"<style>.*?</style>", page, re.S).group(0)
    body = re.search(r"<body>(.*)</body>", page, re.S).group(1)
    app_script = re.search(r"<script>.*?</script>", body, re.S)
    markup, script = body[:app_script.start()], app_script.group(0)
    note = ('<div style="max-width:1280px;margin:12px auto 0;padding:0 24px;font-size:13px;color:#5f6b64">'
            'Demo page of the James app: the same screen, with the fictitious demo ship. Reading your own lab report, '
            'PDF upload and the Word download run in the app itself (start_james.bat). Changes stay in this browser tab.</div>')
    data = json.dumps(demo_data(), ensure_ascii=False).replace("</", "<\\/")
    mock = (HERE / "mock_api.js").read_text(encoding="utf-8")
    OUT.write_text("<title>James Lab Agent</title>\n" + style + "\n" + note + markup
                   + f"<script>window.JAMES_DEMO = {data};</script>\n<script>\n{mock}\n</script>\n" + script + "\n",
                   encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print("written", build())
