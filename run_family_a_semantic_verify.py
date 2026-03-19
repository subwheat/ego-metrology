"""
run_family_a_semantic_verify.py — v2 (prompts durcis)
======================================================
2 politiques sur le corpus Family A figé :
  - qwen_single_pass
  - qwen_semantic_verify_repair (prompts durcis v2)

Durcissements v2 :
  - verify_prompt : sortie binaire stricte PASS/FAIL
  - repair_prompt : interdit toute explication
  - parse_verify_verdict : parse sur premier token uniquement
  - UNPARSED → traité comme FAIL
"""
import os, json, time, re
from openai import OpenAI

MODEL       = "Qwen/Qwen2.5-14B-Instruct"
BASE_URL    = os.environ.get("OPENAI_BASE_URL", "http://51.159.139.27:8000/v1")
CORPUS_FILE = "data/family_a_fixed_v1.json"
OUTPUT_FILE = "runs/family_a_qwen_semantic_verify_v2.jsonl"

TEMPERATURE           = 0.0
MAX_TOKENS_ANSWER     = 16
MAX_TOKENS_VERIFY     = 4
MAX_TOKENS_REPAIR     = 16

C_CONF_BASE = 0.001
MAX_CONTEXT = 16384

def alpha_s(pt): return (pt / MAX_CONTEXT) ** 1.5
def c_dyn(pt):   return pt * C_CONF_BASE * (1 + alpha_s(pt))
def estimate_prompt_tokens(p): return len(p) // 4

# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------
def extract_codes(text):
    hits = re.findall(r'\b[A-Z]{2}-\d{2}\b', text.upper())
    return list(dict.fromkeys(hits))

def score(response, gold, decoys):
    found    = extract_codes(response.strip())
    gold_u   = gold.upper()
    decoys_u = [d.upper() for d in decoys]
    if len(found) == 0:
        return {"is_correct":False,"parsed_value":None, "result":"missed",          "valid_format":False}
    if len(found) > 1:
        return {"is_correct":False,"parsed_value":found,"result":"ambiguous",       "valid_format":False}
    val = found[0]
    if val == gold_u:
        return {"is_correct":True, "parsed_value":val,  "result":"correct",         "valid_format":True}
    if val in decoys_u:
        return {"is_correct":False,"parsed_value":val,  "result":"wrong_condition", "valid_format":True}
    return     {"is_correct":False,"parsed_value":val,  "result":"missed",          "valid_format":True}

# ---------------------------------------------------------------------------
# API helper
# ---------------------------------------------------------------------------
def call(client, prompt, max_tokens):
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
        )
        ans           = resp.choices[0].message.content or ""
        finish_reason = resp.choices[0].finish_reason
        ct = resp.usage.completion_tokens if resp.usage else max(1,len(ans)//4)
        pt = resp.usage.prompt_tokens     if resp.usage else estimate_prompt_tokens(prompt)
    except Exception as e:
        ans,finish_reason,ct,pt = "ERROR","error",0,estimate_prompt_tokens(prompt)
    return ans, finish_reason, ct, pt, round((time.time()-t0)*1000)

# ---------------------------------------------------------------------------
# Prompts durcis v2
# ---------------------------------------------------------------------------
def base_prompt(item):
    return f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"

def verify_prompt(item, candidate_code):
    return f"""{item['context']}

[CHECK]
Candidate code: {candidate_code}

Task:
1. Identify which department has code {candidate_code}.
2. Count how many times that department name appears across ALL sections.
3. Decide whether the count is exactly 2.

Return exactly one token:
PASS
or
FAIL"""

def repair_prompt(item, bad_candidate):
    return f"""{item['context']}

[QUESTION]
Find the department mentioned exactly twice across ALL sections.
Then map that department to its code.
The previous candidate {bad_candidate} is not trusted.
Return exactly one line.
Return exactly one value.
Return only the code in format XX-NN.
Do not explain.
Do not justify.
Do not write anything else.

[ANSWER]"""

def parse_verify_verdict(text):
    u = text.strip().upper().split()
    if not u:
        return "UNPARSED"
    tok = u[0]
    if tok == "PASS": return "PASS"
    if tok == "FAIL": return "FAIL"
    return "UNPARSED"

# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
def policy_single_pass(client, item):
    prompt1 = base_prompt(item)
    ans1,fr1,ct1,pt1,lat1 = call(client, prompt1, MAX_TOKENS_ANSWER)
    sc1 = score(ans1, item["gold"], item["decoys"])
    return {
        "policy_id":"qwen_single_pass","passes":1,
        "semantic_verify_triggered":False,"repair_triggered":False,
        "verify_verdict":None,
        "answer_pass1":ans1[:120],"verify_answer":None,"answer_final":ans1[:120],
        "parsed_value":sc1["parsed_value"],"result":sc1["result"],
        "is_correct":sc1["is_correct"],"valid_format_pass1":sc1["valid_format"],
        "repaired":False,"degraded":False,
        "prompt_tokens":pt1,"completion_tokens":ct1,"total_tokens":pt1+ct1,
        "latency_ms":lat1,"finish_reason":fr1,"cost_dyn":round(c_dyn(pt1),6),
    }

def policy_semantic_verify_repair(client, item):
    # Pass 1 — réponse initiale
    prompt1 = base_prompt(item)
    ans1,fr1,ct1,pt1,lat1 = call(client, prompt1, MAX_TOKENS_ANSWER)
    sc1 = score(ans1, item["gold"], item["decoys"])
    candidate = sc1["parsed_value"] if isinstance(sc1["parsed_value"], str) else None

    # Pass 2 — vérification sémantique si candidat parsable
    verify_triggered = candidate is not None
    if verify_triggered:
        prompt2 = verify_prompt(item, candidate)
        ans2,fr2,ct2,pt2,lat2 = call(client, prompt2, MAX_TOKENS_VERIFY)
        verdict = parse_verify_verdict(ans2)
    else:
        ans2,fr2,ct2,pt2,lat2 = "","",0,0,0
        verdict = "FAIL"

    # Pass 3 — réparation si FAIL ou UNPARSED
    repair_triggered = (verdict != "PASS")
    if repair_triggered:
        bad = candidate if candidate else "NONE"
        prompt3 = repair_prompt(item, bad)
        ans3,fr3,ct3,pt3,lat3 = call(client, prompt3, MAX_TOKENS_REPAIR)
        sc3 = score(ans3, item["gold"], item["decoys"])
        ans_final,sc_final,fr_final = ans3,sc3,fr3
    else:
        ans3,fr3,ct3,pt3,lat3 = "","",0,0,0
        ans_final,sc_final,fr_final = ans1,sc1,fr1

    total_pt = pt1+pt2+pt3
    total_ct = ct1+ct2+ct3
    total_cost = round(c_dyn(pt1)+(c_dyn(pt2) if pt2 else 0)+(c_dyn(pt3) if pt3 else 0),6)

    return {
        "policy_id":"qwen_semantic_verify_repair","passes":1+(1 if verify_triggered else 0)+(1 if repair_triggered else 0),
        "semantic_verify_triggered":verify_triggered,"repair_triggered":repair_triggered,
        "verify_verdict":verdict,
        "answer_pass1":ans1[:120],"verify_answer":ans2[:60] if verify_triggered else None,
        "answer_final":ans_final[:120],
        "parsed_value":sc_final["parsed_value"],"result":sc_final["result"],
        "is_correct":sc_final["is_correct"],"valid_format_pass1":sc1["valid_format"],
        "repaired":(not sc1["is_correct"] and sc_final["is_correct"]),
        "degraded":(sc1["is_correct"] and not sc_final["is_correct"]),
        "prompt_tokens":total_pt,"completion_tokens":total_ct,"total_tokens":total_pt+total_ct,
        "latency_ms":lat1+lat2+lat3,"finish_reason":fr_final,"cost_dyn":total_cost,
    }

POLICY_FNS = {
    "qwen_single_pass":            policy_single_pass,
    "qwen_semantic_verify_repair": policy_semantic_verify_repair,
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run():
    with open(CORPUS_FILE) as f:
        corpus = json.load(f)
    items = corpus["items"]
    total = len(items) * len(POLICY_FNS)
    print(f"\n>>> {len(items)} items × {len(POLICY_FNS)} politiques = ~{total} runs")
    print(f">>> Modèle : {MODEL} — prompts durcis v2\n")

    client = OpenAI(base_url=BASE_URL, api_key="none")
    os.makedirs("runs", exist_ok=True)

    written = 0
    with open(OUTPUT_FILE, "w") as out:
        for pid, fn in POLICY_FNS.items():
            print(f"\n{'='*50}\nPolitique : {pid}\n{'='*50}")
            for item in items:
                res = fn(client, item)
                res.update({
                    "run_id":          f"{pid}__{item['item_id']}",
                    "item_id":         item["item_id"],
                    "level":           item["level"],
                    "noise_paragraphs":item["noise_paragraphs"],
                    "model_name":      MODEL,
                    "alpha_s_est":     round(alpha_s(estimate_prompt_tokens(base_prompt(item))),6),
                })
                out.write(json.dumps(res)+"\n")
                written += 1

                tag = "✓" if res["is_correct"] else ("~" if res["repair_triggered"] else "✗")
                if written % 40 == 0:
                    print(f"  [{written}] {tag} {item['item_id']} | passes={res['passes']} | verdict={res.get('verify_verdict')} | {res['result']} | {res['answer_final'][:24]!r}")
                else:
                    print(f"  {tag}", end="", flush=True)
                time.sleep(0.1)
            print()

    print(f"\n→ {written} runs sauvegardés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
