"""
compare_claude_v4_mini.py
=========================
Mini-sweep niveau 1 uniquement — Family B + C
Modèle : claude-haiku-4-5-20251001 via API Anthropic
But : valider que Family A est une limite Mistral-7B, pas un bug de protocole.
"""
import os,json,time,random,math,re
import anthropic

MODEL="claude-haiku-4-5-20251001"
MAX_TOKENS=20
TEMPERATURE=0.0
RUNS=5
OUTPUT_FILE="calibration_compare_claude_mini.json"
C_CONF_BASE=0.001
MAX_CONTEXT=200_000

def alpha_s(pt): return (pt/MAX_CONTEXT)**1.5
def c_dyn(pt): return pt*C_CONF_BASE*(1+alpha_s(pt))
def estimate_prompt_tokens(p): return len(p)//4

NOISE=[
    "The compliance officer reviewed all pending documentation before the quarterly meeting.",
    "Section 4.2 applies only to entities registered under the interim framework established in 2021.",
    "All protocol identifiers follow the format XX-NN where XX is a two-letter prefix.",
    "The regional task force submitted its findings to the central registry on the designated deadline.",
    "Dept: Phantom | code: ZZ-00 | status: deprecated",
    "Authorization level GOLD applies to senior staff with tenure exceeding 36 months.",
    "Dept: Solaris | code: BX-44 | note: transferred to archive Q2",
    "The blue protocol was superseded by the amber protocol in the revised guidelines.",
    "Role: Auditor | clearance: level-2 | valid_from: 2024-01-01 | valid_until: 2025-12-31",
    "Cross-reference table updated: see Appendix D for current mappings.",
]

def noise(n):
    c=random.sample(NOISE,min(n,len(NOISE)))
    if n>len(NOISE): c+=random.choices(NOISE,k=n-len(NOISE))
    return "\n".join(c)

CONTRACT="""Return exactly one line.
Return exactly one value.
Do not repeat the question.
Do not add labels, quotes, or explanations."""

def extract_b(r):
    hits=re.findall(r'\b[A-Z]+-\d+\b', r.upper())
    return list(dict.fromkeys(hits))

def extract_c(r):
    hits=re.findall(r'\bCLEARANCE-[A-Z]+\b', r.upper())
    return list(dict.fromkeys(hits))

def extract_a(r):
    hits=re.findall(r'\b[A-Z]{2}-\d{2}\b', r.upper())
    return list(dict.fromkeys(hits))

EXTRACTORS={"A":extract_a,"B":extract_b,"C":extract_c}

def score(family, response, gold, decoys):
    r=response.strip()
    found=EXTRACTORS[family](r)
    gold_u=gold.upper()
    decoys_u=[d.upper() for d in decoys]
    if len(found)==0:
        return {"exact_match":0,"wrong_condition":0,"missed":1,"ambiguous":0,"raw":r[:60]}
    if len(found)>1:
        return {"exact_match":0,"wrong_condition":0,"missed":0,"ambiguous":1,"raw":r[:60]}
    val=found[0]
    if val==gold_u:
        return {"exact_match":1,"wrong_condition":0,"missed":0,"ambiguous":0,"raw":r[:60]}
    if val in decoys_u:
        return {"exact_match":0,"wrong_condition":1,"missed":0,"ambiguous":0,"raw":r[:60]}
    return {"exact_match":0,"wrong_condition":0,"missed":1,"ambiguous":0,"raw":r[:60]}

def family_a(n):
    decoys=[("Orion","KQ-17"),("Nyx","TR-91"),("Cetus","WP-04"),("Draco","SN-66")]
    random.shuffle(decoys)
    L=["[SECTION REGISTRY]","Dept: Vega | region: west | status: active"]
    for d,c in decoys[:2]: L.append(f"Dept: {d} | code: {c} | status: active")
    L+=["",noise(n//2) if n else "","","[SECTION CODES]","Dept: Vega | code: LM-22 | status: active"]
    for d,c in decoys[2:]: L.append(f"Dept: {d} | code: {c} | status: active")
    q=f"""{CONTRACT}
Step 1: count how many times each department name appears across ALL sections.
Step 2: identify the department mentioned exactly twice.
Step 3: return its code in format XX-NN.
Only one department appears exactly twice. Return only its code."""
    return {"family":"A","context":"\n".join(L),"question":q,
            "gold":"LM-22","decoys":[c for _,c in decoys]}

def family_b(n):
    entries=[("SECTION LOGISTICS","blue","ALPHA-3"),("SECTION OPERATIONS","red","GAMMA-9"),
             ("SECTION OPERATIONS","blue","DELTA-7"),("SECTION COMPLIANCE","blue","EPSILON-1"),
             ("SECTION OPERATIONS","amber","BETA-2"),("SECTION LOGISTICS","red","ZETA-5")]
    random.shuffle(entries)
    L=[]
    for s,col,p in entries:
        L+=[f"[{s}]",f"color: {col} | protocol: {p}",""]
    if n: L.append(noise(n))
    q=f"""{CONTRACT}
Return only the protocol listed under color BLUE in SECTION OPERATIONS.
Format: WORD-N"""
    return {"family":"B","context":"\n".join(L),"question":q,
            "gold":"DELTA-7","decoys":[p for _,_,p in entries if p!="DELTA-7"]}

def family_c(n):
    entries=[("Manager","2025-01-01","2025-12-31","CLEARANCE-GOLD"),
             ("Manager","2026-01-01","2026-12-31","CLEARANCE-SILVER"),
             ("Auditor","2025-01-01","2025-12-31","CLEARANCE-BRONZE"),
             ("Coordinator","2025-06-01","2026-05-31","CLEARANCE-IRON"),
             ("Observer","2024-01-01","2025-10-31","CLEARANCE-NONE"),
             ("Manager","2023-01-01","2024-12-31","CLEARANCE-EXPIRED")]
    random.shuffle(entries)
    L=["[AUTHORIZATION TABLE]"]
    for role,vf,vu,auth in entries:
        L.append(f"role: {role} | valid_from: {vf} | valid_until: {vu} | authorization: {auth}")
    if n: L+=["",noise(n)]
    q=f"""{CONTRACT}
Target date: 2025-08-15. Target role: Manager.
A row matches if: role is Manager AND valid_from <= 2025-08-15 AND valid_until >= 2025-08-15.
Exactly one row matches. Return only its authorization label.
Format: CLEARANCE-WORD"""
    return {"family":"C","context":"\n".join(L),"question":q,
            "gold":"CLEARANCE-GOLD","decoys":["CLEARANCE-SILVER","CLEARANCE-BRONZE","CLEARANCE-IRON","CLEARANCE-NONE","CLEARANCE-EXPIRED"]}

BUILDERS={"A":family_a,"B":family_b,"C":family_c}

def run():
    api_key=os.environ.get("ANTHROPIC_API_KEY","")
    if not api_key:
        print("ERROR : ANTHROPIC_API_KEY non définie."); return
    client=anthropic.Anthropic(api_key=api_key)
    results=[]

    print(f"\n>>> Mini-sweep niveau 1 — {MODEL}\n")
    for fk in ["A","B","C"]:
        item_fn=BUILDERS[fk]
        successes=[];errs={"wrong_condition":0,"missed":0,"ambiguous":0}
        print(f"  Family {fk}")
        for i in range(RUNS):
            item=item_fn(0)
            prompt=f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"
            pt=estimate_prompt_tokens(prompt);cd=c_dyn(pt)
            try:
                resp=client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    messages=[{"role":"user","content":prompt}])
                ans=resp.content[0].text if resp.content else ""
            except Exception as e:
                print(f"    run {i+1}: ERROR {e}"); ans="ERROR"
            sc=score(fk,ans,item["gold"],item["decoys"])
            successes.append(sc["exact_match"])
            for k in errs: errs[k]+=sc.get(k,0)
            tag="✓" if sc["exact_match"] else ("~" if sc["ambiguous"] else "✗")
            print(f"    run {i+1}: {tag} | {sc['raw']!r} | c_dyn={cd:.3f}")
            time.sleep(0.5)
        sr=sum(successes)/RUNS
        print(f"    → sr={sr:.0%}\n")
        results.append({"family":fk,"model":MODEL,"level":1,"noise":0,
                        "success_rate":round(sr,3),
                        "errors":{k:v/RUNS for k,v in errs.items()}})

    print("\n>>> Comparaison Mistral-7B vs Claude Haiku :")
    mistral={"A":0.0,"B":0.8,"C":0.8}
    for r in results:
        fk=r["family"]
        m=mistral.get(fk,"?")
        c=r["success_rate"]
        delta=f"+{c-m:.0%}" if c>m else f"{c-m:.0%}"
        print(f"  Family {fk} : Mistral={m:.0%}  Claude={c:.0%}  delta={delta}")

    with open(OUTPUT_FILE,"w") as f:
        json.dump({"model":MODEL,"protocol":"v4.3_mini_L1",
                   "mistral_baseline":mistral,"results":results},f,indent=2)
    print(f"\n→ {OUTPUT_FILE} sauvegardé")

if __name__=="__main__":
    random.seed(42);run()
