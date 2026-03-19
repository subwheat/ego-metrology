"""
run_family_a_verify_policies.py
================================
3 politiques sur le corpus Family A figé :
  - qwen_single_pass
  - qwen_verify_pass_always         (2 appels systématiques)
  - qwen_verify_if_invalid          (2ème appel seulement si 1er invalide)

Sortie : runs/family_a_qwen_verify_eval_v1.jsonl
"""
import os, json, time, re, statistics
from openai import OpenAI

MODEL       = "Qwen/Qwen2.5-14B-Instruct"
BASE_URL    = os.environ.get("OPENAI_BASE_URL", "http://51.159.139.27:8000/v1")
CORPUS_FILE = "data/family_a_fixed_v1.json"
OUTPUT_FILE = "runs/family_a_qwen_verify_eval_v1.jsonl"
TEMPERATURE = 0.0
MAX_TOKENS  = 16
C_CONF_BASE = 0.001
MAX_CONTEXT = 16384

def alpha_s(pt): return (pt / MAX_CONTEXT) ** 1.5
def omega_r_proxy(pt): return round(1.0 - alpha_s(pt), 6)
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
    gold_u    = gold.upper()
    decoys_u  = [d.upper() for d in decoys]
    if len(found) == 0:
        return {"is_correct": False, "parsed_value": None,  "result": "missed",    "valid_format": False}
    if len(found) > 1:
        return {"is_correct": False, "parsed_value": found, "result": "ambiguous", "valid_format": False}
    val = found[0]
    if val == gold_u:
        return {"is_correct": True,  "parsed_value": val,   "result": "correct",         "valid_format": True}
    if val in decoys_u:
        return {"is_correct": False, "parsed_value": val,   "result": "wrong_condition", "valid_format": True}
    return     {"is_correct": False, "parsed_value": val,   "result": "missed",          "valid_format": True}

# ---------------------------------------------------------------------------
# API call helper
# ---------------------------------------------------------------------------
def call(client, prompt, max_tokens=MAX_TOKENS):
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
        )
        ans             = resp.choices[0].message.content or ""
        finish_reason   = resp.choices[0].finish_reason
        completion_tok  = resp.usage.completion_tokens if resp.usage else len(ans)//4
        prompt_tok      = resp.usage.prompt_tokens     if resp.usage else estimate_prompt_tokens(prompt)
    except Exception as e:
        ans, finish_reason, completion_tok, prompt_tok = "ERROR", "error", 0, estimate_prompt_tokens(prompt)
    latency_ms = round((time.time() - t0) * 1000)
    return ans, finish_reason, completion_tok, prompt_tok, latency_ms

VERIFY_PROMPT_SUFFIX = (
    "\n\nYour previous answer was not in the correct format or was ambiguous. "
    "Re-check carefully. Count department mentions across ALL sections. "
    "Return only one code in format XX-NN. Nothing else."
)

# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
def policy_single_pass(client, item):
    prompt = f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"
    ans, fr, ct, pt, lat = call(client, prompt)
    sc = score(ans, item["gold"], item["decoys"])
    return {
        "policy_id":          "qwen_single_pass",
        "passes":             1,
        "verified":           False,
        "verify_triggered":   False,
        "answer_pass1":       ans[:120],
        "answer_final":       ans[:120],
        "parsed_value":       sc["parsed_value"],
        "result":             sc["result"],
        "is_correct":         sc["is_correct"],
        "valid_format_pass1": sc["valid_format"],
        "prompt_tokens":      pt,
        "completion_tokens":  ct,
        "total_tokens":       pt + ct,
        "latency_ms":         lat,
        "finish_reason":      fr,
        "cost_dyn":           round(c_dyn(pt), 6),
    }

def policy_verify_always(client, item):
    prompt1 = f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"
    ans1, fr1, ct1, pt1, lat1 = call(client, prompt1)
    sc1 = score(ans1, item["gold"], item["decoys"])

    prompt2 = prompt1 + f"\n{ans1}" + VERIFY_PROMPT_SUFFIX
    ans2, fr2, ct2, pt2, lat2 = call(client, prompt2)
    sc2 = score(ans2, item["gold"], item["decoys"])

    return {
        "policy_id":          "qwen_verify_pass_always",
        "passes":             2,
        "verified":           True,
        "verify_triggered":   True,
        "answer_pass1":       ans1[:120],
        "answer_final":       ans2[:120],
        "parsed_value":       sc2["parsed_value"],
        "result":             sc2["result"],
        "is_correct":         sc2["is_correct"],
        "valid_format_pass1": sc1["valid_format"],
        "repaired":           (not sc1["is_correct"] and sc2["is_correct"]),
        "degraded":           (sc1["is_correct"] and not sc2["is_correct"]),
        "prompt_tokens":      pt1 + pt2,
        "completion_tokens":  ct1 + ct2,
        "total_tokens":       pt1 + ct1 + pt2 + ct2,
        "latency_ms":         lat1 + lat2,
        "finish_reason":      fr2,
        "cost_dyn":           round(c_dyn(pt1) + c_dyn(pt2), 6),
    }

def policy_verify_if_invalid(client, item):
    prompt1 = f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"
    ans1, fr1, ct1, pt1, lat1 = call(client, prompt1)
    sc1 = score(ans1, item["gold"], item["decoys"])

    triggered = not sc1["valid_format"]  # 2ème pass seulement si format invalide

    if triggered:
        prompt2 = prompt1 + f"\n{ans1}" + VERIFY_PROMPT_SUFFIX
        ans2, fr2, ct2, pt2, lat2 = call(client, prompt2)
        sc2 = score(ans2, item["gold"], item["decoys"])
        ans_final, sc_final = ans2, sc2
        total_tok = pt1+ct1+pt2+ct2
        total_lat = lat1+lat2
        cost = round(c_dyn(pt1)+c_dyn(pt2), 6)
        fr_final = fr2
    else:
        ans_final, sc_final = ans1, sc1
        ct2=pt2=lat2=0
        total_tok = pt1+ct1
        total_lat = lat1
        cost = round(c_dyn(pt1), 6)
        fr_final = fr1

    return {
        "policy_id":          "qwen_verify_if_invalid",
        "passes":             2 if triggered else 1,
        "verified":           triggered,
        "verify_triggered":   triggered,
        "answer_pass1":       ans1[:120],
        "answer_final":       ans_final[:120],
        "parsed_value":       sc_final["parsed_value"],
        "result":             sc_final["result"],
        "is_correct":         sc_final["is_correct"],
        "valid_format_pass1": sc1["valid_format"],
        "repaired":           (triggered and not sc1["is_correct"] and sc_final["is_correct"]),
        "degraded":           (triggered and sc1["is_correct"] and not sc_final["is_correct"]),
        "prompt_tokens":      pt1+(pt2 or 0),
        "completion_tokens":  ct1+(ct2 or 0),
        "total_tokens":       total_tok,
        "latency_ms":         total_lat,
        "finish_reason":      fr_final,
        "cost_dyn":           cost,
    }

POLICY_FNS = {
    "qwen_single_pass":         policy_single_pass,
    "qwen_verify_pass_always":  policy_verify_always,
    "qwen_verify_if_invalid":   policy_verify_if_invalid,
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run():
    with open(CORPUS_FILE) as f:
        corpus = json.load(f)
    items  = corpus["items"]
    total  = len(items) * len(POLICY_FNS)
    print(f"\n>>> {len(items)} items × {len(POLICY_FNS)} politiques = ~{total} appels (verify_if_invalid < {total})")
    print(f">>> Modèle : {MODEL}\n")

    client = OpenAI(base_url=BASE_URL, api_key="none")
    os.makedirs("runs", exist_ok=True)

    call_count = 0
    with open(OUTPUT_FILE, "w") as out:
        for pid, fn in POLICY_FNS.items():
            print(f"\n{'='*50}\nPolitique : {pid}\n{'='*50}")
            for item in items:
                result = fn(client, item)
                result.update({
                    "run_id":          f"{pid}__{item['item_id']}",
                    "item_id":         item["item_id"],
                    "level":           item["level"],
                    "noise_paragraphs":item["noise_paragraphs"],
                    "model_name":      MODEL,
                    "alpha_s_est":     round(alpha_s(estimate_prompt_tokens(
                                           f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"
                                       )), 6),
                })
                out.write(json.dumps(result) + "\n")
                call_count += 1

                tag = "✓" if result["is_correct"] else ("~" if result.get("verify_triggered") else "✗")
                if call_count % 50 == 0:
                    print(f"  [{call_count}] {tag} {item['item_id']} | passes={result['passes']} | {result['result']} | {result['answer_final'][:30]!r}")
                else:
                    print(f"  {tag}", end="", flush=True)
                time.sleep(0.1)
            print()

    print(f"\n→ {call_count} runs sauvegardés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
