"""Walk through the whole flow on the fictional ship case:
lab report -> proposals with reasons -> inspector decisions -> draft report -> asset file."""
from ai.james_ai.demo_data import SHIP
from james.store import Store

s = Store()  # in memory; pass a file path to keep the data
oid = s.add_object(SHIP["name"], SHIP["kind"], SHIP["ref"], SHIP["site"], SHIP["project"], SHIP["samples"])

print("== 1. Lab report 1 arrives; the linker proposes")
rid = s.ingest_report(oid, "Lab report 1", SHIP["reports"]["b1"]["text"])
for r in s.rows(rid):
    print(f"  row {r['idx'] + 1}: {r['raw_id'] or '-':6} -> {r['proposed_code'] or 'NO LINK':8} {r['confidence'] or '':7} {r['reason'][:90]}")

print("\n== 2. The inspector decides (nothing is final until this step)")
INSPECTOR = "Inspector (demo)"
for r in s.rows(rid):
    if r["proposed_code"]:
        s.decide(rid, r["idx"], "approved", by=INSPECTOR)
s.decide(rid, 5, "corrected", by=INSPECTOR, sample_code="S-06", note="description matches the steering gear room")
s.decide(rid, 6, "rejected", by=INSPECTOR, note="S-09 is not in the register, ask the lab")

print("\n== 3. Draft report")
d = s.draft_report(rid)
print(f"  {d['object']} at {d['site']} [{d['status']}]")
for x in d["linked"]:
    print(f"  {x['sample']} {x['location']:36} {x['result']}")
print("  Open items:", *d["open_items"], sep="\n   - ")

print("\n== 4. Save to the asset file, then a follow-up report arrives")
s.save_asset_version(oid, rid, INSPECTOR)
r2 = s.ingest_report(oid, "Lab report 2", SHIP["reports"]["b2"]["text"])
s.decide(r2, 0, "approved", by=INSPECTOR)
s.decide(r2, 1, "approved", by=INSPECTOR)
s.save_asset_version(oid, r2, INSPECTOR)
a = s.asset(oid)
print(f"  asset file is at version {a['version']}")
for h in a["samples"]["S-03"]["history"]:
    print(f"  S-03 v{h['version']}: {h['result']}" + ("   <- result changed" if h["changed"] else ""))

print("\n== 5. Audit log")
for e in s.audit_log():
    print(f"  {e['decided_at']}  {e['decided_by']}: row {e['idx'] + 1} {e['state']}"
          f" {e['sample_code'] or ''} {('(' + e['note'] + ')') if e['note'] else ''}")
