"""
run_family_a_policies.py — v2
==============================
Politiques adaptées à Family A (réponse ultra-courte ~2-5 tokens) :
  fixed_cap_4, fixed_cap_8, fixed_cap_16, ego_controller_stub

Controller stub :
  - choisit parmi cap 4/8/16
  - basé sur alpha_S (charge spectatrice estimée)
  - omega_r = 1.0 - alpha_S (proxy jouet, explicitement nommé)
  - loggue la troncature (finish_reason == length)
"""
import os, json, time, re, math
from openai import OpenAI

MODEL = "Qwen/Qwen2.5-14B-Instruct"
BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://51.159.139.27:8000/v1")
CORPUS_FILE = "data/family_a_fixed_v1.json"
OUTPUT_FILE = "runs/family_a_qwen_policy_eval_v1.jsonl"
TEMPERATURE = 0.0
C_CONF_BASE = 0.001
MAX_CONTEXT = 16384

def alpha_s(pt): return (pt / MAX_CONTEXT) ** 1.5
def omega_r_proxy(pt): return round(1.0 - alpha_s(pt), 6)  # proxy jouet, pas Ω_R réel
def c_dyn(pt): return pt * C_CONF_BASE * (1 + alpha_s(pt))
def estimate_prompt_tokens(p): return len(p) // 4

# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------
def extract_a(r):
    hits = re.findall(r'\b[A-Z]{2}-\d{2}\b', r.upper())
    return list(dict.fromkeys(hits))

def score(response, gold, decoys):
    found = extract_a(response.strip())
    gold_u = gold.upper()
    decoys_u = [d.upper() for d in decoys]
    if len(found) == 0:
        return {"is_correct": False, "parsed_value": None, "result": "missed"}
    if len(found) > 1:
        return {"is_correct": False, "parsed_value": found, "result": "ambiguous"}
    val = found[0]
    if val == gold_u:
        return {"is_correct": True,  "parsed_value": val, "result": "correct"}
    if val in decoys_u:
        return {"is_correct": False, "parsed_value": val, "result": "wrong_condition"}
    return {"is_correct": False, "parsed_value": val, "result": "missed"}

# ---------------------------------------------------------------------------
# EGO controller stub v2
# Seuils calibrés sur le corpus Family A :
#   alpha_S typique L1 ≈ 0.001, L4 ≈ 0.003, L7 ≈ 0.008
#   → seuils choisis pour séparer les 3 zones de charge
# ---------------------------------------------------------------------------
class EgoControllerStub:
    def __init__(self):
        self.policy_id = "ego_controller_stub"

    def choose_cap(self, prompt_tokens):
        a = alpha_s(prompt_tokens)
        w = omega_r_proxy(prompt_tokens)
        # faible charge → on peut se permettre cap 16
        # charge moyenne → cap 8
        # charge forte  → cap 4 (économie max)
        if a < 0.002:
            cap = 16
            budget_band = "low"
        elif a < 0.005:
            cap = 8
            budget_band = "medium"
        else:
            cap = 4
            budget_band = "high"
        return cap, a, w, budget_band

POLICIES = [
    {"policy_id": "fixed_cap_4",  "type": "fixed", "cap": 4},
    {"policy_id": "fixed_cap_8",  "type": "fixed", "cap": 8},
    {"policy_id": "fixed_cap_16", "type": "fixed", "cap": 16},
    {"policy_id": "ego_controller_stub", "type": "ego"},
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run():
    with open(CORPUS_FILE) as f:
        corpus = json.load(f)
    items = corpus["items"]
    total = len(items) * len(POLICIES)
    print(f"\n>>> {len(items)} items × {len(POLICIES)} politiques = {total} appels")
    print(f">>> Modèle : {MODEL}\n")

    client = OpenAI(base_url=BASE_URL, api_key="none")
    controller = EgoControllerStub()
    os.makedirs("runs", exist_ok=True)

    call_count = 0
    with open(OUTPUT_FILE, "w") as out:
        for policy in POLICIES:
            pid = policy["policy_id"]
            print(f"\n{'='*50}\nPolitique : {pid}\n{'='*50}")
            for item in items:
                prompt = f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"
                pt = estimate_prompt_tokens(prompt)
                cd = c_dyn(pt)

                if policy["type"] == "fixed":
                    cap = policy["cap"]
                    a = alpha_s(pt)
                    w = omega_r_proxy(pt)
                    budget_band = "n/a"
                else:
                    cap, a, w, budget_band = controller.choose_cap(pt)

                t0 = time.time()
                try:
                    resp = client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=TEMPERATURE,
                        max_tokens=cap,
                    )
                    ans = resp.choices[0].message.content or ""
                    finish_reason = resp.choices[0].finish_reason
                    completion_tokens = resp.usage.completion_tokens if resp.usage else len(ans)//4
                except Exception as e:
                    ans = "ERROR"; finish_reason = "error"; completion_tokens = 0
                    print(f"  ERROR: {e}")
                latency_ms = round((time.time() - t0) * 1000)

                sc = score(ans, item["gold"], item["decoys"])
                truncated = (finish_reason == "length")

                record = {
                    "run_id":            f"{pid}__{item['item_id']}",
                    "item_id":           item["item_id"],
                    "level":             item["level"],
                    "noise_paragraphs":  item["noise_paragraphs"],
                    "model_name":        MODEL,
                    "policy_id":         pid,
                    "token_cap":         cap,
                    "budget_band":       budget_band,
                    "alpha_s_est":       round(a, 6),
                    "omega_r_proxy":     w,
                    "answer_raw":        ans[:120],
                    "parsed_value":      sc["parsed_value"],
                    "result":            sc["result"],
                    "is_correct":        sc["is_correct"],
                    "truncated":         truncated,
                    "prompt_tokens":     pt,
                    "completion_tokens": completion_tokens,
                    "latency_ms":        latency_ms,
                    "finish_reason":     finish_reason,
                    "cost_dyn":          round(cd, 6),
                    "cost_tokens":       pt + completion_tokens,
                }
                out.write(json.dumps(record) + "\n")
                call_count += 1

                tag = "✓" if sc["is_correct"] else ("T" if truncated else "✗")
                if call_count % 50 == 0 or finish_reason == "error":
                    print(f"  [{call_count}/{total}] {tag} {item['item_id']} | cap={cap} | {sc['result']} | {ans[:40]!r}")
                else:
                    print(f"  {tag}", end="", flush=True)
                time.sleep(0.15)
            print()

    print(f"\n→ {call_count} runs sauvegardés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
