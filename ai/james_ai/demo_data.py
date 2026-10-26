"""Fictional demo cases. Structure follows RVL's project dossiers; every name,
code and result value is made up, and the problems in the lab text are planted
on purpose so the linker can be tested."""
from .linker import Sample

SHIP = {
    "name": "MV Demo Star", "kind": "Ship", "ref": "IMO 0000000 (fictional)",
    "site": "Quay 12, Demo Harbour", "project": "26-3VK",
    "samples": [
        Sample("S-01", "B-01", "Engine room, port bulkhead", "Bulkhead", "Insulation wrap", "grey fibrous", "IMG_0101"),
        Sample("S-02", "B-02", "Engine room, main engine exhaust", "Exhaust pipe", "Pipe lagging", "white", "IMG_0107"),
        Sample("S-03", "B-03", "Boiler room, boiler door", "Boiler door", "Gasket", "black", "IMG_0112"),
        Sample("S-04", "B-04", "Accommodation deck 2, corridor", "Ceiling", "Ceiling panel", "white-grey board", "IMG_0120"),
        Sample("S-05", "B-05", "Accommodation deck 2, cabin 214", "Floor", "Floor covering", "green vinyl", "IMG_0126"),
        Sample("S-06", "B-06", "Steering gear room", "Pipe flange", "Flange gasket", "grey", "IMG_0133"),
        Sample("S-07", "B-07", "Cargo hold 1", "Bulkhead", "Paint coating", "red-brown", "IMG_0140"),
        Sample("S-08", "B-08", "Pump room", "Pump", "Pump packing", "grey-white woven", "IMG_0148"),
    ],
    "reports": {
        "b1": {
            "text": "\n".join([
                "Report: LAB-2026-0412", "Lab: Demo Lab (ISO 17025, fictional)", "Project: 26-3VK",
                "Vessel: MV Demo Star", "---",
                "S-01 | Insulation wrap, engine room bulkhead | Chrysotile 15%",
                "S02 | Exhaust pipe lagging, engine room | Asbestos not detected",
                "s-03 | Boiler door gasket, black | Chrysotile 40%",
                "S 04 | Ceiling panel, corridor deck 2 | Asbestos not detected",
                "S-05 | Floor covering cabin 214, green vinyl | Chrysotile 2%",
                "S-05 | Flange gasket, steering gear room | Asbestos not detected",
                "S-09 | Hatch coaming seal, hold 2 | Asbestos not detected",
                "- | Pump packing, pump room, grey-white woven | Asbestos not detected",
                "S-07 | Bulkhead coating, cargo hold 1, red-brown | Asbestos not detected"]),
            # reference links as an inspector would verify them (None = no sample exists)
            "truth": {0: "S-01", 1: "S-02", 2: "S-03", 3: "S-04", 4: "S-05", 5: "S-06",
                      6: None, 7: "S-08", 8: "S-07"},
        },
        "b2": {
            "text": "\n".join([
                "Report: LAB-2026-0498", "Lab: Demo Lab (ISO 17025, fictional)", "Project: 26-3VK",
                "Vessel: MV Demo Star", "---",
                "S-06 | Flange gasket, steering gear room | Asbestos not detected",
                "S-03 | Boiler door gasket, black | Chrysotile 35% (re-analysis)"]),
            "truth": {0: "S-06", 1: "S-03"},
        },
    },
}

VIADUCT = {
    "name": "Demo viaduct", "kind": "Civil structure", "ref": "Object 00X-000 (fictional)",
    "site": "Motorway corridor, km 22.0 (anonymised)", "project": "26-4QX",
    "samples": [
        Sample("CH6-01", "KW-01", "Sheet pile wall, km 22.1", "Sheet pile wall", "Coating", "grey, 2 layers", "IMG_2201"),
        Sample("CH6-02", "KW-02", "Sheet pile wall at lamp post", "Sheet pile wall", "Coating", "grey, 2 layers", "IMG_2209"),
        Sample("CH6-03", "KW-03", "Noise barrier", "Noise barrier", "Coating", "blue, 4 layers", "IMG_2216"),
        Sample("CH6-05", "KW-05", "Column 2, mid bearing", "Bearing", "Coating", "black/orange, 2 layers", "IMG_2230"),
        Sample("CH6-06", "KW-06", "Column 2, concrete", "Concrete column", "Red primer", "red, 2 layers", "IMG_2236"),
        Sample("CH6-08", "KW-08", "Column 3, concrete", "Concrete column", "Red primer", "red, 2 layers", "IMG_2251"),
        Sample("CH6-10", "KW-10", "Railing, noise barrier side", "Railing", "Coating", "white", "IMG_2270"),
        Sample("CH6-11", "KW-11", "Railing posts", "Railing posts", "Coating", "orange, 3 layers", "IMG_2278"),
        Sample("CH6-14", "KW-14", "Abutment bearing", "Bearing", "Coating", "black, 2 layers", "IMG_2301"),
    ],
    "reports": {
        "b1": {
            "text": "\n".join([
                "Report: LAB-2026-0377", "Lab: Demo Lab (fictional)", "Project: 26-4XQ", "---",
                "CH6-01 | Sheet pile wall, grey, 2 layers | Cr(VI) 8 mg/kg; Pb 120 mg/kg",
                "CH6-02 | Sheet pile wall at lamp post, grey | Cr(VI) <5 mg/kg; Pb 40 mg/kg",
                "CH6-03 | Noise barrier, blue, 4 layers | Cr(VI) 310 mg/kg; Pb 2100 mg/kg",
                "CH6-5 | Column 2 bearing, black orange | Cr(VI) 45 mg/kg; Pb 900 mg/kg",
                "GS15 | Concrete column, red primer, 2 layers | Cr(VI) 15 mg/kg; Pb 640 mg/kg",
                "CH6-11 | Railing posts, orange, 3 layers | Cr(VI) 22 mg/kg; Pb 1500 mg/kg",
                "CH6-14 | Abutment bearing, black, 2 layers | Cr(VI) <5 mg/kg; Pb 85 mg/kg",
                "CH6-13 | Railing posts, orange, 3 layers | Cr(VI) 19 mg/kg; Pb 1400 mg/kg"]),
            "truth": {0: "CH6-01", 1: "CH6-02", 2: "CH6-03", 3: "CH6-05", 4: "CH6-06",
                      5: "CH6-11", 6: "CH6-14", 7: None},
        },
    },
}
