"""
run_family_a_extract_then_check.py
=================================
2 politiques sur le corpus Family A figé :
  - qwen_single_pass
  - qwen_extract_then_check

Idée :
- baseline : réponse directe XX-NN
- politique structurée :
    pass 1 = extraire le département mentionné exactement 2 fois
    check programmatique = compter les mentions + mapper au code
"""

import os, json, time, re
from collections import Counter, defaultdict
from openai import OpenAI

MODEL       = "Qwen/Qwen2.5-14B-Instruct"
BASE_URL    = os.environ.get("OPENAI_BASE_URL", "http://51.159.139.27:8000/v1")
CORPUS_FILE = "data/family_a_fixed_v2.json"
OUTPUT_FILE = "runs/family_a_qwen_extract_then_check_v2.jsonl"

TEMPERATURE = 0.0
MAX_TOKENS_ANSWER = 16
MAX_TOKENS_EXTRACT = 8

C_CONF_BASE = 0.001
MAX_CONTEXT = 16384

def alpha_s(pt): return (pt / MAX_CONTEXT) ** 1.5
def c_dyn(pt): return pt * C_CONF_BASE * (1 + alpha_s(pt))
def estimate_prompt_tokens(p): return len(p) // 4

# ---------------------------------------------------------------------------
# Generic scorer for baseline XX-NN
# ---------------------------------------------------------------------------
def extract_codes(text):
    hits = re.findall(r'\b[A-Z]{2}-\d{2}\b', text.upper())
    return list(dict.fromkeys(hits))

def score_code(response, gold, decoys):
    found = extract_codes(response.strip())
    gold_u = gold.upper()
    decoys_u = [d.upper() for d in decoys]

    if len(found) == 0:
        return {
            "is_correct": False,
            "parsed_value": None,
            "result": "missed",
            "valid_format": False,
        }

    if len(found) > 1:
        return {
            "is_correct": False,
            "parsed_value": found,
            "result": "ambiguous",
            "valid_format": False,
        }

    val = found[0]
    if val == gold_u:
        return {
            "is_correct": True,
            "parsed_value": val,
            "result": "correct",
            "valid_format": True,
        }

    if val in decoys_u:
        return {
            "is_correct": False,
            "parsed_value": val,
            "result": "wrong_condition",
            "valid_format": True,
        }

    return {
        "is_correct": False,
        "parsed_value": val,
        "result": "missed",
        "valid_format": True,
    }

# ---------------------------------------------------------------------------
# Programmatic checker
# ---------------------------------------------------------------------------
DEPT_LINE_RE = re.compile(
    r'^\s*Dept:\s*([A-Za-z]+)\b(?:\s*\|\s*code:\s*([A-Z]{2}-\d{2}))?',
    re.IGNORECASE
)

def parse_context_structure(context):
    mentions = []
    codes = defaultdict(list)

    for raw_line in context.splitlines():
        m = DEPT_LINE_RE.match(raw_line.strip())
        if not m:
            continue
        dept = m.group(1)
        code = m.group(2)
        dept_norm = dept.strip().title()
        mentions.append(dept_norm)
        if code:
            codes[dept_norm].append(code.upper())

    counts = Counter(mentions)

    unique_codes = {}
    for dept, vals in codes.items():
        uniq = sorted(set(vals))
        if len(uniq) == 1:
            unique_codes[dept] = uniq[0]

    return counts, unique_codes

def parse_department_answer(answer, valid_departments):
    text = answer.strip()
    if not text:
        return None

    # 1) match exact department names present in context
    hits = []
    for dept in valid_departments:
        if re.search(rf'\b{re.escape(dept)}\b', text, flags=re.IGNORECASE):
            hits.append(dept)

    hits = list(dict.fromkeys(hits))
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        return None

    # 2) fallback: single capitalized token
    m = re.search(r'\b([A-Z][a-z]+)\b', text)
    if m:
        cand = m.group(1).title()
        if cand in valid_departments:
            return cand

    return None

# ---------------------------------------------------------------------------
# API helper
# ---------------------------------------------------------------------------
def call(client, prompt, max_tokens):
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
        )
        ans = resp.choices[0].message.content or ""
        finish_reason = resp.choices[0].finish_reason
        completion_tok = resp.usage.completion_tokens if resp.usage else max(1, len(ans)//4)
        prompt_tok = resp.usage.prompt_tokens if resp.usage else estimate_prompt_tokens(prompt)
    except Exception:
        ans = "ERROR"
        finish_reason = "error"
        completion_tok = 0
        prompt_tok = estimate_prompt_tokens(prompt)

    latency_ms = round((time.time() - t0) * 1000)
    return ans, finish_reason, completion_tok, prompt_tok, latency_ms

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
def base_prompt(item):
    return f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"

def extract_prompt(item):
    return f"""{item['context']}

[QUESTION]
Find the department name mentioned exactly twice across ALL sections.

Return exactly one line.
Return only the department name.
Do not return a code.
Do not explain.
Do not write anything else.

[ANSWER]"""

# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
def policy_single_pass(client, item):
    prompt1 = base_prompt(item)
    ans1, fr1, ct1, pt1, lat1 = call(client, prompt1, MAX_TOKENS_ANSWER)
    sc1 = score_code(ans1, item["gold"], item["decoys"])

    return {
        "policy_id": "qwen_single_pass",
        "passes": 1,
        "answer_pass1": ans1[:120],
        "answer_final": ans1[:120],
        "parsed_value": sc1["parsed_value"],
        "result": sc1["result"],
        "is_correct": sc1["is_correct"],
        "prompt_tokens": pt1,
        "completion_tokens": ct1,
        "total_tokens": pt1 + ct1,
        "latency_ms": lat1,
        "finish_reason": fr1,
        "cost_dyn": round(c_dyn(pt1), 6),
    }

def policy_extract_then_check(client, item):
    counts, code_map = parse_context_structure(item["context"])
    valid_departments = sorted(counts.keys())

    prompt1 = extract_prompt(item)
    ans1, fr1, ct1, pt1, lat1 = call(client, prompt1, MAX_TOKENS_EXTRACT)

    extracted_dept = parse_department_answer(ans1, valid_departments)

    if extracted_dept is None:
        result = "invalid_extract"
        mapped_code = None
        mention_count = None
        is_correct = False
    else:
        mention_count = counts.get(extracted_dept, 0)
        mapped_code = code_map.get(extracted_dept)

        if mention_count != 2:
            result = "wrong_condition"
            is_correct = False
        elif mapped_code is None:
            result = "missing_code_map"
            is_correct = False
        elif mapped_code == item["gold"]:
            result = "correct"
            is_correct = True
        else:
            result = "wrong_code_map"
            is_correct = False

    final_answer = mapped_code if mapped_code is not None and mention_count == 2 else (ans1[:120] if ans1 else "")

    return {
        "policy_id": "qwen_extract_then_check",
        "passes": 1,
        "answer_pass1": ans1[:120],
        "answer_final": str(final_answer)[:120],
        "extracted_department": extracted_dept,
        "checker_mention_count": mention_count,
        "checker_mapped_code": mapped_code,
        "parsed_value": mapped_code if mapped_code is not None else extracted_dept,
        "result": result,
        "is_correct": is_correct,
        "prompt_tokens": pt1,
        "completion_tokens": ct1,
        "total_tokens": pt1 + ct1,
        "latency_ms": lat1,
        "finish_reason": fr1,
        "cost_dyn": round(c_dyn(pt1), 6),
    }

POLICY_FNS = {
    "qwen_single_pass": policy_single_pass,
    "qwen_extract_then_check": policy_extract_then_check,
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
    print(f">>> Modèle : {MODEL} — structured extract-then-check — corpus validated_v2\n")

    client = OpenAI(base_url=BASE_URL, api_key="none")
    os.makedirs("runs", exist_ok=True)

    written = 0
    with open(OUTPUT_FILE, "w") as out:
        for pid, fn in POLICY_FNS.items():
            print(f"\n{'='*50}\nPolitique : {pid}\n{'='*50}")
            for item in items:
                prompt_alpha = base_prompt(item)
                alpha_est = round(alpha_s(estimate_prompt_tokens(prompt_alpha)), 6)

                res = fn(client, item)
                res.update({
                    "run_id": f"{pid}__{item['item_id']}",
                    "item_id": item["item_id"],
                    "level": item["level"],
                    "noise_paragraphs": item["noise_paragraphs"],
                    "model_name": MODEL,
                    "alpha_s_est": alpha_est,
                })

                out.write(json.dumps(res) + "\n")
                written += 1

                tag = "✓" if res["is_correct"] else "✗"
                if written % 40 == 0:
                    extra = ""
                    if pid == "qwen_extract_then_check":
                        extra = f" | dept={res.get('extracted_department')} | count={res.get('checker_mention_count')} | code={res.get('checker_mapped_code')}"
                    print(f"  [{written}] {tag} {item['item_id']} | {res['result']}{extra} | {str(res['answer_final'])[:24]!r}")
                else:
                    print(f"  {tag}", end="", flush=True)
                time.sleep(0.1)
            print()

    print(f"\n→ {written} runs sauvegardés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
