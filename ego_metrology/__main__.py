from __future__ import annotations
import sys
import json
from .profiler import EgoProfiler, SECTOR_CONFIGS

def main():
    args = sys.argv[1:]

    if not args or "--help" in args:
        print("\nUsage: python -m ego_metrology <model> <tokens> [--json]")
        print("Ex:    python -m ego_metrology deepseek-14b 12000")
        print("Ex:    python -m ego_metrology deepseek-14b 12000 --json\n")
        sys.exit(0)

    if "--list" in args:
        for k, v in SECTOR_CONFIGS.items():
            print(f"  {k:<20} max={v.max_context_tokens:,} tokens  [{v.calibration_status}]")
        sys.exit(0)

    use_json = "--json" in args
    args = [a for a in args if a != "--json"]

    if len(args) < 2:
        print("Erreur : donne un modèle et un nombre de tokens.")
        sys.exit(1)

    try:
        tokens = int(args[1])
    except ValueError:
        print(f"Erreur : '{args[1]}' n'est pas un entier valide.")
        sys.exit(1)

    try:
        result = EgoProfiler(args[0]).profile(tokens)
    except (ValueError, TypeError) as e:
        print(f"Erreur : {e}")
        sys.exit(1)

    if use_json:
        output = {
            "model":               result.model,
            "prompt_tokens":       result.prompt_tokens,
            "max_context_tokens":  result.max_context_tokens,
            "eta":                 result.eta,
            "alpha_s":             result.alpha_s,
            "r_eta":               result.r_eta,
            "geometric_status":    result.geometric_regime,
            "c_dyn":               result.c_dyn,
            "tau":                 result.tau,
            "calibration_status":  result.calibration_status,
        }
        print(json.dumps(output, indent=2))
    else:
        print(result.summary())

if __name__ == "__main__":
    main()
