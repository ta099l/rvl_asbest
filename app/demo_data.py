"""Fictitious demo ship for the app, the same one as the demo artifact (MV Noorderlicht).

Every name, code, number and result is made up. The problems are planted on
purpose: a lab ID written differently (M-03), a result for a sample nobody
registered (MM-9), a sample without a result (MM-4), a missing photo and drawing position (ODS-1), a
missing certificate number (HM-1) and a place that could not be sampled (MM-5).
"""
from ai.james_ai.linker import Sample

NOT_SAMPLED = "not sampled"

SHIP = {
    "name": "MV Noorderlicht", "kind": "General cargo · NL", "ref": "IMO 9000000 (fictitious)",
    "site": "Shipyard, Rotterdam", "project": "J-26-014", "survey_date": "6 Oct 2026",
    "info": {"client": "Example Shipping B.V. (fictitious)", "client_address": "Harbour Street 1, Exampletown",
             "owner": "Example Owner Ltd. (fictitious)", "owner_address": "Quay Road 2, Exampleport",
             "surveyor": "A. Surveyor (fictitious)", "technical_responsible": "B. Reviewer (fictitious)",
             "project_coordinator": "C. Coordinator (fictitious)", "survey_period": "6–7 Oct 2026"},
    "samples": [
        Sample("MM-1", "B01", "Engine room, exhaust pipe", "Exhaust pipe", "Insulation", "white braided", "F-012", deck="Deck 2", drawing="GA-02 pos 4", quantity="12", unit="m"),
        Sample("MM-2", "B02", "Accommodation, cabin 3.04", "Floor", "Floor tile", "beige", "F-018", deck="Deck 3", drawing="GA-03 pos 11", quantity="18", unit="m2"),
        Sample("MM-3", "B03", "Steering gear room, flange", "Flange", "Gasket", "black", "F-024", deck="Deck 1", drawing="GA-01 pos 2", quantity="4", unit="pcs"),
        Sample("MM-4", "B04", "Engine room, bulkhead", "Bulkhead", "Fire-resistant board", "grey", "F-031", deck="Deck 2", drawing="GA-02 pos 6", quantity="6", unit="m2"),
        Sample("PBS-1", "B05", "Engine room, cable bundle CB-7", "Cable bundle", "Cable sheathing", "black", "F-040", deck="Deck 2", drawing="GA-02 pos 8", quantity="35", unit="kg"),
        Sample("OS-1", "B06", "Engine room, transformer T1", "Transformer", "Cooling oil", "amber", "F-044", deck="Deck 2", drawing="GA-02 pos 9", quantity="420", unit="l"),
        Sample("ODS-1", "B07", "Galley, cold room", "Cold room", "Insulation foam", "yellow PU", "", deck="Deck 3", quantity="8", unit="m2"),
        Sample("HM-1", "B08", "Railing port side", "Railing", "Paint layer (3 coats)", "red-grey", "F-051", deck="Main deck", drawing="GA-04 pos 1", quantity="40", unit="m2"),
        Sample("PBS-2", "B09", "Bridge, window", "Window", "Window rubber", "black", "F-057", deck="Deck 4", drawing="GA-05 pos 3", quantity="2", unit="kg"),
        Sample("MM-5", "B10", "Void space behind engine room panel", "Pipe", "Pipe insulation", "", "", deck="Deck 1", drawing="GA-01 pos 5", quantity="3", unit="m",
               status=NOT_SAMPLED, restriction="No access: void space behind a welded panel"),
    ],
    "reports": {
        "b1": {
            "label": "Lab report L-26-4471",
            "text": "\n".join([
                "Report: L-26-4471", "Lab: Example Lab Ltd. (ISO 17025, fictitious)", "Project: J-26-014",
                "Vessel: MV Noorderlicht",
                "Columns: Sample No. | Description | Analysis | Result | Certificate",
                "---",
                "MM-1 | White insulation | Asbestos (NEN 5896) | Chrysotile 10–15% | C-4471-01",
                "MM-2 | Floor tile | Asbestos (NEN 5896) | Asbestos not detected | C-4471-01",
                "M-03 | Gasket | Asbestos (NEN 5896) | Chrysotile + amosite 5–10% | C-4471-01",
                "PBS-1 | Cable sheathing | PCB (7 congeners) | 85 mg/kg | C-4471-02",
                "OS-1 | Transformer oil | PCB | < 2 mg/kg (DL 2) | C-4471-02",
                "ODS-1 | PU foam | ODS (GC-MS) | CFC-11 detected | C-4471-03",
                "HM-1 | Railing paint | Heavy metals | Lead 1400 mg/kg |",
                "PBS-2 | Window rubber | PCB (7 congeners) | < 2 mg/kg (DL 2) | C-4471-02",
                "MM-9 | Board, grey | Asbestos (NEN 5896) | Asbestos not detected | C-4471-01",
            ]),
        },
        "b2": {
            "label": "Follow-up L-26-4590",
            "text": "\n".join([
                "Report: L-26-4590", "Lab: Example Lab Ltd. (ISO 17025, fictitious)", "Project: J-26-014",
                "Vessel: MV Noorderlicht",
                "Columns: Sample No. | Description | Analysis | Result | Certificate",
                "---",
                "MM-4 | Fire-resistant board, grey | Asbestos (NEN 5896) | Asbestos not detected | C-4590-01",
                "MM-3 | Gasket, re-analysis | Asbestos (NEN 5896) | Chrysotile + amosite 8% | C-4590-01",
            ]),
        },
    },
}
