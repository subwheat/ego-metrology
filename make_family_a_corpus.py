"""
make_family_a_corpus.py
=======================
Génère un corpus Family A fixe et VALIDÉ.
Invariant :
- Vega apparaît exactement 2 fois
- aucun autre département n'apparaît 2 fois ou plus

Sortie :
  data/family_a_fixed_v2.json
"""
import json
import random
import os
import re
from collections import Counter

LEVELS = [
    {"level": 1, "n": 0},
    {"level": 2, "n": 3},
    {"level": 3, "n": 8},
    {"level": 4, "n": 18},
    {"level": 5, "n": 40},
    {"level": 6, "n": 80},
    {"level": 7, "n": 140},
]

ITEMS_PER_LEVEL = 30
OUTPUT = "data/family_a_fixed_v2.json"

# Bruit neutre : duplicable sans danger
NEUTRAL_NOISE = [
    "The compliance officer reviewed all pending documentation before the quarterly meeting.",
    "Section 4.2 applies only to entities registered under the interim framework established in 2021.",
    "The regional task force submitted its findings to the central registry on the designated deadline.",
    "Cross-reference table updated: see Appendix D for current mappings.",
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
    "The quarterly audit confirmed compliance across all registered operational units.",
    "Retrieval requests must reference the primary registry entry, not the archive.",
    "Legacy records must not be used to determine current eligibility.",
    "The oversight committee reviews archive consistency every quarter.",
    "Any unresolved discrepancy must be escalated to the central registry.",
]

# Bruit avec départements : autorisé AU PLUS UNE FOIS par item
DEPT_NOISE = [
    "Dept: Phantom | code: ZZ-00 | status: deprecated",
    "Dept: Solaris | code: BX-44 | note: transferred to archive Q2",
    "Dept: Kronos | code: MV-55 | note: seasonal activation only",
    "Dept: Lyra | code: CW-19 | status: active | region: north",
    "Dept: Cygnus | code: FT-88 | note: observer-only access",
    "Dept: Boreas | code: RX-03 | status: active | region: east",
    "Dept: Zephyr | code: NL-77 | status: inactive | note: pending review",
    "Dept: Aether | code: GK-12 | status: active | region: south",
]

CONTRACT = """Return exactly one line.
Return exactly one value.
Do not repeat the question.
Do not add labels, quotes, or explanations."""

DEPT_LINE_RE = re.compile(r'^\s*Dept:\s*([A-Za-z]+)\b', re.IGNORECASE)

def parse_dept_counts(context: str) -> Counter:
    counts = Counter()
    for line in context.splitlines():
        m = DEPT_LINE_RE.match(line.strip())
        if m:
            counts[m.group(1).title()] += 1
    return counts

def validate_item(item):
    counts = parse_dept_counts(item["context"])

    if counts.get("Vega", 0) != 2:
        raise ValueError(
            f"{item['item_id']} invalide : Vega count = {counts.get('Vega', 0)}"
        )

    bad = {dept: c for dept, c in counts.items() if dept != "Vega" and c >= 2}
    if bad:
        raise ValueError(f"{item['item_id']} invalide : autres depts >=2 => {bad}")

def gen_noise_lines(n, rng):
    if n <= 0:
        return []

    # Nombre max de lignes Dept: uniques par item
    max_dept_lines = min(len(DEPT_NOISE), max(0, n // 6))
    dept_count = rng.randint(0, max_dept_lines) if max_dept_lines > 0 else 0

    dept_lines = rng.sample(DEPT_NOISE, dept_count)
    neutral_count = n - dept_count

    # Le neutre peut être dupliqué sans casser l'invariant
    if neutral_count <= len(NEUTRAL_NOISE):
        neutral_lines = rng.sample(NEUTRAL_NOISE, neutral_count)
    else:
        neutral_lines = []
        while len(neutral_lines) < neutral_count:
            neutral_lines.extend(rng.sample(NEUTRAL_NOISE, len(NEUTRAL_NOISE)))
        neutral_lines = neutral_lines[:neutral_count]

    lines = dept_lines + neutral_lines
    rng.shuffle(lines)
    return lines

def build_item(level, n, item_idx, rng):
    decoys = [("Orion", "KQ-17"), ("Nyx", "TR-91"), ("Cetus", "WP-04"), ("Draco", "SN-66")]
    rng.shuffle(decoys)

    noise_lines = gen_noise_lines(n, rng)
    split = len(noise_lines) // 2
    noise_1 = noise_lines[:split]
    noise_2 = noise_lines[split:]

    L = ["[SECTION REGISTRY]", "Dept: Vega | region: west | status: active"]
    for d, c in decoys[:2]:
        L.append(f"Dept: {d} | code: {c} | status: active")

    if noise_1:
        L += [""] + noise_1

    L += ["", "[SECTION CODES]", "Dept: Vega | code: LM-22 | status: active"]
    for d, c in decoys[2:]:
        L.append(f"Dept: {d} | code: {c} | status: active")

    if noise_2:
        L += [""] + noise_2

    question = f"""{CONTRACT}
Step 1: count how many times each department name appears across ALL sections.
Step 2: identify the department mentioned exactly twice.
Step 3: return its code in format XX-NN.
Only one department appears exactly twice. Return only its code."""

    item = {
        "item_id": f"A_L{level}_{item_idx:03d}",
        "family": "A",
        "rule": "count+bind",
        "level": level,
        "noise_paragraphs": n,
        "context": "\n".join(L),
        "question": question,
        "gold": "LM-22",
        "decoys": [c for _, c in decoys],
    }

    validate_item(item)
    return item

def main():
    rng = random.Random(42)
    corpus = []

    for lv in LEVELS:
        level, n = lv["level"], lv["n"]
        for i in range(ITEMS_PER_LEVEL):
            corpus.append(build_item(level, n, i + 1, rng))
        print(f"  Level {level} (noise={n}) — {ITEMS_PER_LEVEL} items générés et validés")

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(
            {
                "meta": {
                    "family": "A",
                    "levels": len(LEVELS),
                    "items_per_level": ITEMS_PER_LEVEL,
                    "total_items": len(corpus),
                    "noise_version": "validated_v2",
                    "seed": 42,
                    "invariant": "Vega exactly twice; all others < 2",
                },
                "items": corpus,
            },
            f,
            indent=2,
        )

    print(f"\n→ {len(corpus)} items sauvegardés dans {OUTPUT}")
    print("  Invariant vérifié sur tous les items.")

if __name__ == "__main__":
    main()
