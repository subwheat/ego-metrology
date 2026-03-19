"""
make_family_a_corpus.py
=======================
Génère un corpus Family A fixe — 30 items par niveau, 7 niveaux = 210 items.
Sauvegarde dans data/family_a_fixed_v1.json
À exécuter une seule fois. Ne pas regénérer entre les runs de politiques.
"""
import json, random, os

LEVELS = [
    {"level":1,"n":0},{"level":2,"n":3},{"level":3,"n":8},{"level":4,"n":18},
    {"level":5,"n":40},{"level":6,"n":80},{"level":7,"n":140},
]
ITEMS_PER_LEVEL = 30
OUTPUT = "data/family_a_fixed_v1.json"

NOISE = [
    "The compliance officer reviewed all pending documentation before the quarterly meeting.",
    "Section 4.2 applies only to entities registered under the interim framework established in 2021.",
    "The regional task force submitted its findings to the central registry on the designated deadline.",
    "Cross-reference table updated: see Appendix D for current mappings.",
    "Dept: Phantom | code: ZZ-00 | status: deprecated",
    "Dept: Solaris | code: BX-44 | note: transferred to archive Q2",
    "Dept: Kronos | code: MV-55 | note: seasonal activation only",
    "Dept: Lyra | code: CW-19 | status: active | region: north",
    "Dept: Cygnus | code: FT-88 | note: observer-only access",
    "Section 7 describes conditions under which exceptions may be granted by the review board.",
    "All entries marked archived are excluded from active protocol resolution.",
    "Authorization requests must include a counter-signature from the compliance lead.",
    "Section 2 applies to all operational units except those under temporary suspension.",
    "Section 9 defines the escalation path for unresolved conditional authorizations.",
    "Role: Auditor | clearance: level-2 | valid_from: 2024-01-01 | valid_until: 2024-12-31",
    "Role: Observer | clearance: level-0 | valid_from: 2023-03-01 | valid_until: 2024-09-01",
    "Role: Coordinator | clearance: level-1 | valid_from: 2022-07-01 | valid_until: 2023-06-30",
    "Role: Analyst | clearance: level-1 | valid_from: 2023-01-01 | valid_until: 2024-01-01",
    "The framework update in late 2022 introduced revised escalation procedures.",
    "All binding decisions require documented approval from the oversight committee.",
    "Dept: Boreas | code: RX-03 | status: active | region: east",
    "Dept: Zephyr | code: NL-77 | status: inactive | note: pending review",
    "Dept: Aether | code: GK-12 | status: active | region: south",
    "The quarterly audit confirmed compliance across all registered operational units.",
    "Retrieval requests must reference the primary registry entry, not the archive.",
]

CONTRACT = """Return exactly one line.
Return exactly one value.
Do not repeat the question.
Do not add labels, quotes, or explanations."""

def gen_noise(n, rng):
    c = rng.sample(NOISE, min(n, len(NOISE)))
    if n > len(NOISE):
        c += rng.choices(NOISE, k=n-len(NOISE))
    return "\n".join(c)

def build_item(level, n, item_idx, rng):
    decoys = [("Orion","KQ-17"),("Nyx","TR-91"),("Cetus","WP-04"),("Draco","SN-66")]
    rng.shuffle(decoys)
    L = ["[SECTION REGISTRY]", "Dept: Vega | region: west | status: active"]
    for d,c in decoys[:2]:
        L.append(f"Dept: {d} | code: {c} | status: active")
    L += ["", gen_noise(n//2, rng) if n else "", "", "[SECTION CODES]",
          "Dept: Vega | code: LM-22 | status: active"]
    for d,c in decoys[2:]:
        L.append(f"Dept: {d} | code: {c} | status: active")
    L += ["", gen_noise(n-n//2, rng) if n else ""]

    question = f"""{CONTRACT}
Step 1: count how many times each department name appears across ALL sections.
Step 2: identify the department mentioned exactly twice.
Step 3: return its code in format XX-NN.
Only one department appears exactly twice. Return only its code."""

    return {
        "item_id": f"A_L{level}_{item_idx:03d}",
        "family": "A",
        "rule": "count+bind",
        "level": level,
        "noise_paragraphs": n,
        "context": "\n".join(L),
        "question": question,
        "gold": "LM-22",
        "decoys": [c for _,c in decoys],
    }

def main():
    rng = random.Random(42)
    corpus = []
    for lv in LEVELS:
        level, n = lv["level"], lv["n"]
        for i in range(ITEMS_PER_LEVEL):
            item = build_item(level, n, i+1, rng)
            corpus.append(item)
        print(f"  Level {level} (noise={n}) — {ITEMS_PER_LEVEL} items générés")

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"meta": {"family":"A","levels":len(LEVELS),
                            "items_per_level":ITEMS_PER_LEVEL,
                            "total_items":len(corpus),
                            "noise_version":"decontaminated_v1",
                            "seed":42},
                   "items": corpus}, f, indent=2)

    print(f"\n→ {len(corpus)} items sauvegardés dans {OUTPUT}")
    print("  Ne pas regénérer ce fichier entre les runs de politiques.")

if __name__ == "__main__":
    main()
