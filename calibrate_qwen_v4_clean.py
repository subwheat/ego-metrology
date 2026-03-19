import os,json,time,random,math,re
from openai import OpenAI
import numpy as np

MODEL="Qwen/Qwen2.5-14B-Instruct"
BASE_URL="http://51.159.139.27:8000/v1"
MAX_CONTEXT=16384;TEMPERATURE=0.0;MAX_TOKENS=20;RUNS_PER_LEVEL=10
OUTPUT_FILE="calibration_qwen_v4_clean.json"
C_CONF_BASE=0.001;A_SECTEUR=1.0;BETA_SECTEUR=0.001

def alpha_s(pt): return (pt/MAX_CONTEXT)**1.5
def c_dyn(pt): return pt*C_CONF_BASE*(1+alpha_s(pt))
def log_tau_predicted(c): return A_SECTEUR-BETA_SECTEUR*c
def estimate_prompt_tokens(p): return len(p)//4

# NOISE décontaminé :
# - pas de Dept Vega
# - pas de role Manager
# - pas de dates couvrant 2025-08-15
# - pas de protocoles de forme WORD-N trop proches des cibles
NOISE=[
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

def noise(n):
    c=random.sample(NOISE,min(n,len(NOISE)))
    if n>len(NOISE): c+=random.choices(NOISE,k=n-len(NOISE))
    return "\n".join(c)

CONTRACT="""Return exactly one line.
Return exactly one value.
Do not repeat the question.
Do not add labels, quotes, or explanations."""

def extract_a(r):
    hits=re.findall(r'\b[A-Z]{2}-\d{2}\b', r.upper())
    return list(dict.fromkeys(hits))

def extract_b(r):
    hits=re.findall(r'\b[A-Z]+-\d+\b', r.upper())
    return list(dict.fromkeys(hits))

def extract_c(r):
    hits=re.findall(r'\bCLEARANCE-[A-Z]+\b', r.upper())
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
    L+=["",noise(n-n//2) if n else ""]
    q=f"""{CONTRACT}
Step 1: count how many times each department name appears across ALL sections.
Step 2: identify the department mentioned exactly twice.
Step 3: return its code in format XX-NN.
Only one department appears exactly twice. Return only its code."""
    return {"family":"A","rule":"count+bind","context":"\n".join(L),"question":q,
            "gold":"LM-22","decoys":[c for _,c in decoys]}

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
        if random.random()<0.3 and n: L.append(noise(2))
    if n: L+=["",noise(n)]
    q=f"""{CONTRACT}
Target date: 2025-08-15. Target role: Manager.
A row matches if: role is Manager AND valid_from <= 2025-08-15 AND valid_until >= 2025-08-15.
Exactly one row matches. Return only its authorization label.
Format: CLEARANCE-WORD"""
    return {"family":"C","rule":"date+role->auth","context":"\n".join(L),"question":q,
            "gold":"CLEARANCE-GOLD","decoys":["CLEARANCE-SILVER","CLEARANCE-BRONZE","CLEARANCE-IRON","CLEARANCE-NONE","CLEARANCE-EXPIRED"]}

BUILDERS={"A":family_a,"C":family_c}
LEVELS=[{"level":1,"n":0},{"level":2,"n":3},{"level":3,"n":8},{"level":4,"n":18},
        {"level":5,"n":40},{"level":6,"n":80},{"level":7,"n":140}]

def run():
    client=OpenAI(base_url=BASE_URL, api_key="none")
    results=[]
    print(f"\n>>> RERUN PROPRE — A+C — {MODEL} — 2×7×10 = 140 appels\n")
    for fk in ["A","C"]:
        print(f"\n{'='*50}\nFamily {fk}\n{'='*50}")
        for lv in LEVELS:
            level,n=lv["level"],lv["n"]
            successes=[];errs={"wrong_condition":0,"missed":0,"ambiguous":0};pts=[];cds=[]
            print(f"\n  Level {level} (noise={n})")
            for i in range(RUNS_PER_LEVEL):
                item=BUILDERS[fk](n)
                prompt=f"{item['context']}\n\n[QUESTION]\n{item['question']}\n\n[ANSWER]"
                pt=estimate_prompt_tokens(prompt);cd=c_dyn(pt)
                pts.append(pt);cds.append(cd)
                try:
                    r=client.chat.completions.create(model=MODEL,
                        messages=[{"role":"user","content":prompt}],
                        temperature=TEMPERATURE,max_tokens=MAX_TOKENS)
                    ans=r.choices[0].message.content or ""
                except Exception as e:
                    print(f"    run {i+1}: ERROR {e}"); ans="ERROR"
                sc=score(fk,ans,item["gold"],item["decoys"])
                successes.append(sc["exact_match"])
                for k in errs: errs[k]+=sc.get(k,0)
                tag="✓" if sc["exact_match"] else ("~" if sc["ambiguous"] else "✗")
                print(f"    run {i+1}: {tag} | {sc['raw']!r} | c_dyn={cd:.3f}")
                time.sleep(0.2)
            avg_pt=sum(pts)/len(pts);avg_cd=sum(cds)/len(cds)
            sr=sum(successes)/RUNS_PER_LEVEL
            lt=math.log(max(sr,1e-6)*100+1e-6)
            results.append({"family":fk,"rule":item["rule"],"level":level,"noise":n,
                            "avg_prompt_tokens":round(avg_pt),"avg_c_dyn":round(avg_cd,6),
                            "success_rate":round(sr,3),"log_tau_obs":round(lt,4),
                            "log_tau_pred":round(log_tau_predicted(avg_cd),4),
                            "errors":{k:v/RUNS_PER_LEVEL for k,v in errs.items()}})
            print(f"    → sr={sr:.0%} | c_dyn={avg_cd:.4f} | log_tau={lt:.3f}")

    print(f"\n{'='*50}\nFits + monotonicité\n{'='*50}")
    fits={}
    for fk in ["A","C"]:
        rows=[r for r in results if r["family"]==fk]
        xs=np.array([r["avg_c_dyn"] for r in rows])
        ys=np.array([r["log_tau_obs"] for r in rows])
        sl,ic=np.polyfit(xs,ys,1)
        diffs=[ys[i+1]-ys[i] for i in range(len(ys)-1)]
        n_down=sum(1 for d in diffs if d<0)
        fits[fk]={"slope":round(float(sl),6),"intercept":round(float(ic),4),
                  "a_secteur_candidate":round(float(ic),4),
                  "beta_secteur_candidate":round(float(-sl),6)}
        verdict="✓ fit légitime" if sl<-0.0001 and n_down>=4 else "⚠ fit prématuré"
        print(f"\n  Family {fk}: slope={sl:+.6f} | {n_down}/6 descendants | {verdict}")
        if sl<-0.0001 and n_down>=4:
            print(f"    a_secteur_candidate  = {ic:.4f}")
            print(f"    beta_secteur_candidate = {-sl:.6f}")

    with open(OUTPUT_FILE,"w") as f:
        json.dump({"meta":{"protocol":"v4.4_qwen_clean","model":MODEL,
                           "noise_version":"decontaminated_v1",
                           "total_calls":2*len(LEVELS)*RUNS_PER_LEVEL},
                   "fits":fits,"results":results},f,indent=2)
    print(f"\n→ {OUTPUT_FILE} sauvegardé")
    print("\n⚠️  Pense à éteindre l'instance H100 sur Scaleway dès que terminé.")

if __name__=="__main__":
    random.seed(42);run()
