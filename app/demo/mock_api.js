// A stand-in for app/server.py, so the real app screen (app/static/index.html) runs as a
// standalone demo page. The linker's proposals come from the real Python app (DEMO, written by
// build_artifact.py); this file only keeps state in the browser and rebuilds the views the
// server would send. Reading your own lab report, PDF upload and the Word download need the
// real app and give a clear message instead.
(() => {
  const DEMO = window.JAMES_DEMO;
  const NOT_SAMPLED = "not sampled";
  const APP_ONLY = "This needs the James app on a laptop (start_james.bat): the linker and the Word export run in Python. This demo page shows the flow with the demo ship.";
  const EDITABLE = ["source", "location", "part", "material", "notes", "photo", "deck", "status", "restriction", "drawing", "quantity", "unit"];
  const INFO = ["client", "client_address", "owner", "owner_address", "surveyor", "technical_responsible", "project_coordinator", "survey_period"];
  window.confirm = () => true;              // the demo viewer has no dialogs; resetting a demo is harmless

  const pad = n => String(n).padStart(2, "0");
  const now = () => { const d = new Date(); return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`; };
  const clone = x => JSON.parse(JSON.stringify(x));
  const norm = c => (c || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  class ApiError extends Error {}
  const fail = m => { throw new ApiError(m); };

  let st;
  function reset() {
    st = { objects: [], current: null, reports: [], nextReport: 1, nextObject: 1 };
    const o = addObject(DEMO.object, DEMO.register, DEMO.info);
    st.demoObject = o.id;
    loadDemo("b1");
  }
  function addObject(f, register, info) {
    const o = { id: st.nextObject++, name: f.name, kind: f.kind || "", ref: f.ref || "", site: f.site, project: f.project,
                survey_date: f.survey_date || "", info: Object.fromEntries(INFO.map(k => [k, (info || {})[k] || ""])),
                register: clone(register || []), log: [], regRev: 0, asset: [] };
    st.objects.push(o); st.current = o.id; return o;
  }
  const obj = () => st.objects.find(o => o.id === st.current);
  const sampled = o => o.register.filter(s => s.status !== NOT_SAMPLED);

  function loadDemo(key, practice) {
    const o = obj();
    if (o.id !== st.demoObject) fail("the demo reports belong to the demo ship; switch to it first");
    const snap = practice ? DEMO.practice : DEMO.reports[key];
    const r = { id: st.nextReport++, object: o.id, label: snap.label, ref: snap.ref, lab: snap.lab, ingested_at: now(),
                rows: clone(snap.rows), evidence: clone(snap.evidence), ai_note: snap.ai_note, decisions: {}, declog: [],
                agent: snap.agent.map(t => ({ at: now(), by: "Agent", text: t })), signed: null, readRev: o.regRev,
                seeded: practice ? clone(DEMO.practice.seeded) : null };
    st.reports.push(r); return r.id;
  }

  // ---------- the IHM reading, as app/ihm.py ----------
  const SECTIONS = [["2.3.1", "Asbestos", ["asbestos"]], ["2.3.2", "PCB's", ["pcb"]], ["2.3.3", "Ozone Depleting Substances (ODS)", ["ods"]],
    ["2.3.4", "PFOS", ["pfos"]], ["2.3.5", "HBCDD", ["hbcdd"]], ["2.3.6", "Heavy metals (Lead - Pb + Chromium - Cr + Cadmium - Cd)", ["pb", "cr6", "cd", "hg"]],
    ["2.3.7", "Radioactive Materials", ["radio"]], ["2.3.x", "Other substances (not a section in the template)", ["tbt", null]]];
  const LINES = [["A-1 Asbestos", "A", ["asbestos"]], ["A-2 Polychlorinated Biphenyls (PCB)", "A", ["pcb"]], ["A-3 Ozone Depleting Substances (ODS)", "A", ["ods"]],
    ["A-4 Anti-fouling Systems Containing Organotin Compounds", "A", ["tbt"]], ["B1 Hexavalent Chromium, B2 Cadmium", "B", ["cr6", "cd"]],
    ["B3 Lead – Paint", "B", ["pb"], "paint"], ["B3 Lead – Batteries", "B", ["pb"], "battery"], ["HBCDD", "B", ["hbcdd"]],
    ["Radioactive Materials", "B", ["radio"]], ["Mercury", "B", ["hg"]]];
  const PART_I = { "I-1": "Paints and Coating Systems", "I-2": "Equipment and Machinery", "I-3": "Structure and Hull" };
  const PAINT = /paint|coating|primer|varnish|lacquer/i;
  const EQUIPMENT = /pump|transformer|cable|engine|motor|generator|compressor|valve|switchboard|boiler|cold room|refrigerat|freezer|air.?condition|radar|battery|fan/i;
  const sectionOf = key => SECTIONS.find(s => s[2].includes(key))[0];
  const partI = s => PAINT.test(s.material || "") ? "I-1" : EQUIPMENT.test(`${s.part} ${s.material}`) ? "I-2" : "I-3";
  const tableLine = (key, s) => { const l = LINES.find(([, , keys, t]) => keys.includes(key) && (!t || (t === "paint" ? PAINT.test(s.material || "") : /batter/i.test(`${s.material} ${s.part}`)))); return l ? l[0] : null; };
  const sampleType = code => ({ KM: "Asbestos dust sample", SS: "PCB surface wipe sample", OS: "PCB oil sample", V: "Visual registration" })[((code || "").match(/^[A-Za-z]+/) || [""])[0].toUpperCase()] || "Bulk material sample";
  function sumQty(list) {
    const units = new Set(list.map(([, u]) => (u || "").trim().toLowerCase()));
    if (units.size !== 1 || units.has("") || list.some(([q]) => !/^\d+([.,]\d+)?$/.test(String(q || "").trim()))) return [null, ""];
    const t = list.reduce((a, [q]) => a + parseFloat(String(q).replace(",", ".")), 0);
    return [Math.round(t * 100) / 100, [...units][0]];
  }

  // ---------- the view, as Service.report_view in app/server.py ----------
  function reportView(r) {
    const o = st.objects.find(x => x.id === r.object), regBy = Object.fromEntries(o.register.map(s => [s.code, s]));
    const rows = r.rows.map(b => {
      const p = b.proposal, s = p.sample ? regBy[p.sample] : null, d = r.decisions[b.idx];
      const { rules_code, ...base } = b;               // rules_code is internal: the server does not send it
      return { ...base, chain: s ? { sample: s.code, source: s.source, deck: s.deck, location: s.location,
                                   material: [s.material, s.notes].filter(Boolean).join(", "), photo: s.photo, ship: o.name } : null,
        checks: s ? [{ ok: b.raw_id === s.code, text: b.raw_id === s.code ? "ID written exactly as in the field registration" : `ID written “${b.raw_id || "none"}”, registration says ${s.code}` },
                     { ok: true, text: "Sample exists in the register" }, { ok: !!s.photo, text: s.photo ? "Photo on file" : "Photo missing" },
                     { ok: !!b.certificate, text: b.certificate ? "Certificate number on the lab line" : "No certificate number" }] : [],
        decision: d ? { state: d.state, sample: d.sample, by: d.by, at: d.at, note: d.note } : null };
    });
    const flags = flagsFor(o, rows), ihm = sections(r, o, rows, regBy);
    const counts = { total: rows.length, certain: rows.filter(x => x.proposal.label === "certain").length,
      check: rows.filter(x => x.proposal.label === "check").length, none: rows.filter(x => x.proposal.label === "none").length,
      decided: rows.filter(x => x.decision).length, linked: rows.filter(x => x.decision && x.decision.state !== "rejected").length };
    const open = [];
    if (counts.decided < counts.total) open.push(`${counts.total - counts.decided} lab line(s) still need an inspector decision.`);
    flags.filter(f => f.kind === "missing" || f.kind === "completeness").forEach(f => open.push(`${f.ref}: ${f.text}`));
    ihm.manual.forEach(m => open.push(`${m.sample}: ${m.note}`));
    [...ihm.table_a, ...ihm.table_b].filter(x => x.found && x.quantity === null)
      .forEach(x => open.push(`${x.line} (Table ${x.table}): quantity and unit to be filled in by the inspector (not every source of ${x.samples.join(", ")} has a quantity in the same unit).`));
    const audit = [...r.declog, ...r.agent];
    if (r.signed) audit.push({ at: r.signed.at, by: r.signed.by, text: `signed the report sections (${r.signed.open_items.length} open item(s) recorded)` });
    audit.sort((a, b) => a.at < b.at ? -1 : a.at > b.at ? 1 : 0);
    const last = r.declog.map(e => e.at).sort().pop();
    const finished = counts.decided === counts.total && last ? last : null;
    return { id: r.id, label: r.label, ref: r.ref, lab: r.lab, evidence: r.evidence, stale: o.regRev > r.readRev && !r.signed,
      practice: !!r.seeded, practice_score: practiceScore(r, rows), rows, counts, flags, ai_note: r.ai_note, ihm, open_items: open,
      signed: r.signed, audit, timing: { started: r.ingested_at, finished, minutes: finished ? Math.round((new Date(finished.replace(" ", "T") + "Z") - new Date(r.ingested_at.replace(" ", "T") + "Z")) / 6000) / 10 : null } };
  }

  function flagsFor(o, rows) {
    const out = [], smp = sampled(o);
    const linked = new Set(rows.map(r => r.proposal.sample).filter(Boolean));
    const decided = new Set(rows.filter(r => r.decision && r.decision.sample).map(r => r.decision.sample));
    rows.forEach(r => {
      const p = r.proposal;
      if (p.sample && r.raw_id && r.raw_id !== p.sample) out.push({ kind: "notation", ref: r.raw_id, line: r.n, text: `Sample ID “${r.raw_id}” differs from the field notation ${p.sample}.` });
      if (!p.sample && r.raw_id) out.push(smp.some(s => norm(s.code) === norm(r.raw_id))
        ? { kind: "conflict", ref: r.raw_id, line: r.n, text: `Line ${r.n}: the ID ${r.raw_id} and the description point to different samples. The inspector decides.` }
        : { kind: "unknown", ref: r.raw_id, line: r.n, text: `Lab result ${r.raw_id} does not belong to any known sample.` });
      if (!p.sample && !r.raw_id) out.push({ kind: "unknown", ref: `line ${r.n}`, line: r.n, text: "Lab line has no sample ID and no safe match." });
      if (p.sample && !r.certificate) out.push({ kind: "completeness", ref: r.raw_id || `line ${r.n}`, line: r.n, text: "No certificate number on this lab line. Needed for the full chain sample → certificate." });
    });
    smp.forEach(s => {
      if (!linked.has(s.code) && !decided.has(s.code)) out.push({ kind: "missing", ref: s.code, line: null, text: `Sample ${s.code} (${(s.material || "").toLowerCase()}, ${s.location}) has no lab result.` });
      else if (!s.photo) out.push({ kind: "completeness", ref: s.code, line: null, text: `No photo ID for ${s.code}. Required for the Materials List (photo + location for every hazardous material).` });
      if ((linked.has(s.code) || decided.has(s.code)) && !s.drawing) out.push({ kind: "completeness", ref: s.code, line: null, text: `No drawing position for ${s.code}. Needed to find the source back on the ship.` });
    });
    o.register.filter(s => s.status === NOT_SAMPLED).forEach(s => out.push({ kind: "limitation", ref: s.code, line: null,
      text: `${s.location} was not sampled (${s.restriction || "no reason given"}). Listed under survey limitations as potentially hazardous.` }));
    return out;
  }

  function sections(r, o, rows, regBy) {
    const secs = Object.fromEntries(SECTIONS.map(([no, title]) => [no, { no, title, samples: [], records: [], lab: [] }]));
    const part1 = { "I-1": [], "I-2": [], "I-3": [] }, lines = {}, manual = [];
    rows.forEach(x => {
      const d = x.decision;
      if (!d || d.state === "rejected") return;
      const s = regBy[d.sample], qty = `${s.quantity || ""} ${s.unit || ""}`.trim(), where = [s.deck, s.location].filter(Boolean).join(" › ");
      x.findings.forEach(f => {
        const sec = secs[sectionOf(f.key)], listed = f.status === "above" || f.status === "at";
        sec.samples.push({ sample: s.code, deck: s.deck, location: s.location, material: [s.material, s.notes].filter(Boolean).join(", "), type: sampleType(s.code), result: f.text });
        sec.records.push({ source: s.source || "–", description: [s.part, s.material].filter(Boolean).join(", "), sample: s.code, certificate: x.certificate,
          location: where, material: s.material, result: f.text, quantity: qty, photo: s.photo, drawing: s.drawing, listed,
          conclusion: listed || f.status === "below" ? `This concerns ${f.name}: ${f.note}.` : `${f.name}: ${f.note}` });
        sec.lab.push({ sample: s.code, certificate: x.certificate, method: x.method, result: f.text, remarks: x.remarks, quantity: x.quantity || qty });
        if (listed) {
          part1[partI(s)].push({ sample: s.code, part: s.part, material: s.material, location: where, materials: f.name, quantity: qty,
                                 remarks: f.note, table: f.table, at_threshold: f.status === "at" });
          const label = tableLine(f.key, s);
          if (!label) manual.push({ sample: s.code, result: f.text, note: `${f.name} has no line in Table A or B of the template: the inspector decides where it goes` });
          else { const l = lines[label] = lines[label] || { samples: [], q: [] }; l.samples.push(s.code); l.q.push([s.quantity, s.unit]); }
        } else if (f.status === "unknown") manual.push({ sample: s.code, result: f.text, note: f.note });
      });
    });
    Object.values(part1).forEach(l => l.forEach((x, i) => x.no = i + 1));
    const tables = { A: [], B: [] };
    LINES.forEach(([label, t]) => { const l = lines[label], [q, u] = l ? sumQty(l.q) : [null, ""];
      tables[t].push({ line: label, table: t, samples: l ? l.samples : [], quantity: q, unit: u, found: !!l }); });
    const info = o.info, versions = r.signed ? 1 : 0;
    const project = [["Project Number", o.project], ["Survey Location", o.site], ["Vessel Name", o.name], ["Vessel Type", o.kind],
      ["Client", info.client], ["Client Address", info.client_address], ["Owner", info.owner], ["Owner Address", info.owner_address],
      ["Contractor", "James"], ["Survey Period", info.survey_period || o.survey_date], ["Survey Conducted By", info.surveyor],
      ["Technical Responsible Person", info.technical_responsible], ["Project Coordinator", info.project_coordinator],
      ["Report Status", r.signed ? "Final" : "Draft"], ["Report Version", String(versions)], ["Report Valid Until", ""]];
    const limitations = o.register.filter(s => s.status === NOT_SAMPLED).map((s, i) => ({ no: i + 1, sample: s.code, deck: s.deck, location: s.location,
      material: s.material, restriction: s.restriction || "Not sampled", follow_up: "Treat as potentially containing hazardous materials (PCHM) until sampled" }));
    return { project, sections: Object.values(secs), part1, part1_titles: PART_I, limitations, table_a: tables.A, table_b: tables.B, manual };
  }

  function practiceScore(r, rows) {
    if (!r.seeded) return null;
    const seeded = Object.entries(r.seeded);
    if (rows.some(x => !x.decision)) return { done: false, seeded: seeded.length };
    const missed = seeded.filter(([i, wrong]) => { const d = r.decisions[i]; return d.state !== "rejected" && d.sample === wrong; })
      .map(([i, wrong]) => ({ line: +i + 1, seeded: wrong, raw_id: r.rows[i].raw_id }));
    const found = seeded.length - missed.length;
    return { done: true, seeded: seeded.length, found, missed, target: "at least 80% (K10)", passed: found >= 0.8 * seeded.length };
  }

  function view(rid) {
    const o = obj(), reports = st.reports.filter(r => r.object === o.id);
    const r = reports.find(x => x.id === rid) || reports[reports.length - 1];
    return {
      object: { id: o.id, name: o.name, kind: o.kind, ref: o.ref, site: o.site, project: o.project, survey_date: o.survey_date, demo: o.id === st.demoObject },
      objects: st.objects.map(x => ({ id: x.id, name: x.name, project: x.project })),
      register: o.register.map(s => ({ ...s, missing: s.status === "sampled" ? [["source", s.source], ["deck", s.deck], ["photo", s.photo], ["drawing", s.drawing]].filter(([, v]) => !v).map(([k]) => k) : [] })),
      register_log: o.log, reports: reports.map(x => ({ id: x.id, label: x.label, report_ref: x.ref, lab: x.lab, ingested_at: x.ingested_at, practice: !!x.seeded })),
      report: r ? reportView(r) : null, asset: assetView(o), thresholds_note: "Thresholds: to confirm by RVL (app/thresholds.json)." };
  }

  function assetView(o) {
    const samples = {};
    o.asset.forEach(v => v.entries.forEach(e => {
      const s = o.register.find(x => x.code === e.sample) || {};
      (samples[e.sample] = samples[e.sample] || { source: s.source, location: s.location, history: [] }).history.push({ version: v.version, ...e });
    }));
    return { object: o.name, site: o.site, version: o.asset.length, samples };
  }

  // ---------- actions, as the POST routes of the server ----------
  const report = rid => st.reports.find(r => r.id === +rid) || fail("unknown report");
  function decide(b) {
    const by = (b.by || "").trim(); if (!by) fail("enter the inspector name first: every decision is signed");
    const r = report(b.report_id); if (r.signed) fail("this report is signed: decisions can no longer change");
    const idx = +b.idx, row = r.rows[idx], p = row.proposal, o = st.objects.find(x => x.id === r.object);
    let d;
    if (b.action === "approve") {
      if (!p.sample) fail("nothing is proposed for this line, so it cannot be approved: link it yourself or reject");
      if (p.sample === row.rules_code) d = { state: "approved", sample: p.sample, note: b.note || "" };
      else if (r.seeded && idx in r.seeded) d = { state: "corrected", sample: p.sample, note: b.note || "" };
      else d = { state: "corrected", sample: p.sample, note: `${b.note ? b.note + " " : ""}approved the ${p.source} proposal; rules alone proposed ${row.rules_code || "no link"}` };
    } else if (b.action === "correct") {
      if (!sampled(o).some(s => s.code === b.sample)) fail(`unknown sample '${b.sample}', or a place that was not sampled`);
      d = { state: "corrected", sample: b.sample, note: b.note || "" };
    } else if (b.action === "reject") d = { state: "rejected", sample: null, note: b.note || "" };
    else fail("unknown action");
    d.by = by; d.at = now(); r.decisions[idx] = d;
    r.declog.push({ at: d.at, by, text: `line ${idx + 1} ${d.state}` + (d.sample ? ` → ${d.sample}` : " (no link)") + (d.note ? ` · ${d.note}` : "") });
    const sc = practiceScore(r, reportView(r).rows);
    if (sc && sc.done) r.agent.push({ at: now(), by: "Agent", text: `Practice result: ${sc.found} of ${sc.seeded} deliberate errors found.` });
    return r.id;
  }
  function checkSample(s) {
    const miss = [["code", s.code], ["location", s.location], ["material", s.material]].filter(([, v]) => !(v || "").trim()).map(([k]) => k);
    if (miss.length) fail("a sample needs " + miss.join(", "));
    if (s.status === NOT_SAMPLED && !(s.restriction || "").trim()) fail("a place that was not sampled needs the reason (it goes to the survey limitations)");
  }
  function addSample(b) {
    const by = (b.by || "").trim(); if (!by) fail("a named inspector is required");
    const o = obj(), s = { code: (b.code || "").trim(), ...Object.fromEntries(EDITABLE.map(k => [k, (b[k] || "").trim()])) };
    s.status = s.status || "sampled"; checkSample(s);
    if (o.register.some(x => x.code === s.code)) fail(`sample code ${s.code} is already registered for this object; codes must be unique`);
    o.register.push(s); o.regRev++;
    o.log.push({ at: now(), by, code: s.code, action: "added", detail: `${s.material} at ${s.location}` + (s.status === NOT_SAMPLED ? ` (${s.status}: ${s.restriction})` : "") });
  }
  function updateSample(b) {
    const by = (b.by || "").trim(); if (!by) fail("a named inspector is required");
    const o = obj(), old = o.register.find(x => x.code === b.code) || fail(`unknown sample '${b.code}'`);
    const neu = { ...old }; EDITABLE.forEach(k => { if (k in b) neu[k] = (b[k] || "").trim(); }); checkSample(neu);
    const linked = st.reports.some(r => r.object === o.id && Object.values(r.decisions).some(d => d.state !== "rejected" && d.sample === old.code));
    if (neu.status === NOT_SAMPLED && old.status !== NOT_SAMPLED && linked) fail(`${old.code} already has a linked lab result, so it cannot become 'not sampled'`);
    const diffs = EDITABLE.filter(k => (old[k] || "") !== (neu[k] || "")).map(k => `${k}: ${old[k] || "–"} -> ${neu[k] || "–"}`);
    if (!diffs.length) return;
    Object.assign(old, neu); o.regRev++;
    o.log.push({ at: now(), by, code: old.code, action: "changed", detail: diffs.join("; ") });
  }
  function sign(b) {
    const r = report(b.report_id), by = (b.by || "").trim();
    if (r.seeded) fail("a practice report cannot be signed");
    if (r.signed) fail("this report is already signed");
    if (!by) fail("a named inspector is required");
    const v = reportView(r);
    if (v.counts.decided < v.counts.total) fail(`${v.counts.total - v.counts.decided} lab line(s) still need a decision before signing`);
    r.signed = { by, at: now(), open_items: v.open_items };
    r.agent.push({ at: r.signed.at, by: "Agent", text: `Signed by ${by} as Technical Responsible Person. Report status: Final.` });
    return r.id;
  }
  function saveHistory(b) {
    const r = report(b.report_id), by = (b.by || "").trim(); if (!by) fail("enter the inspector name first");
    if (r.seeded) fail("a practice report never goes into the ship's history");
    const o = st.objects.find(x => x.id === r.object), links = Object.entries(r.decisions).filter(([, d]) => d.state !== "rejected");
    if (!links.length) fail("no approved links to save");
    const prev = assetView(o).samples;
    o.asset.push({ version: o.asset.length + 1, entries: links.map(([i, d]) => { const h = (prev[d.sample] || { history: [] }).history, res = r.rows[i].result;
      return { sample: d.sample, result: res, approved_by: d.by, approved_at: d.at, via: d.state, changed: !!h.length && h[h.length - 1].result !== res }; }) });
    return r.id;
  }
  function newProject(b) {
    if (!(b.name || "").trim() || !(b.project || "").trim() || !(b.site || "").trim()) fail("a project needs a name, a project number and a survey location");
    addObject({ name: b.name.trim(), kind: b.kind, ref: b.ref, site: b.site.trim(), project: b.project.trim(), survey_date: b.survey_date }, [], b);
  }

  const ROUTES = {
    "/api/reset": () => { reset(); return null; },
    "/api/demo": b => loadDemo(b.which || "b1"),
    "/api/practice": () => loadDemo("b1", true),
    "/api/report": () => fail(APP_ONLY), "/api/upload-pdf": () => fail(APP_ONLY),
    "/api/reread": b => { const r = report(b.report_id); if (r.signed) fail("this report is signed; its proposals can no longer change");
                          r.readRev = st.objects.find(o => o.id === r.object).regRev;
                          r.agent.push({ at: now(), by: "Agent", text: "Read again with the current field registration (in this demo page the proposals stay the same; the app runs the linker again)." }); return r.id; },
    "/api/decide": decide, "/api/sign": sign, "/api/save-history": saveHistory,
    "/api/project": b => { newProject(b); return null; },
    "/api/select-project": b => { if (!st.objects.some(o => o.id === +b.object_id)) fail("unknown project"); st.current = +b.object_id; return null; },
    "/api/sample": b => { addSample(b); return b.report_id; }, "/api/sample-update": b => { updateSample(b); return b.report_id; },
  };
  const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: async () => clone(body), headers: { get: () => null } });

  window.fetch = (url, opt) => {
    const [path, q] = String(url).split("?");
    try {
      if (path === "/api/state") { const m = (q || "").match(/report=(\d+)/); return reply(200, view(m ? +m[1] : null)); }
      if (path === "/api/export") return reply(400, { error: APP_ONLY });
      const route = ROUTES[path];
      if (!route) return reply(404, { error: "not found" });
      const rid = route(opt && opt.body ? JSON.parse(opt.body) : {});
      return reply(200, view(rid ? +rid : null));
    } catch (e) {
      if (e instanceof ApiError) return reply(400, { error: e.message });
      throw e;
    }
  };
  reset();
})();
