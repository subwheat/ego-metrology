from __future__ import annotations
import sys
from .profiler import EgoProfiler, SECTOR_CONFIGS

def main():
    args = sys.argv[1:]
    if not args or "--help" in args:
        print("\nUsage: python -m ego_metrology <model> <tokens>\nEx:    python -m ego_metrology deepseek-14b 12000\n")
        sys.exit(0)
    if "--list" in args:
        for k, v in SECTOR_CONFIGS.items():
            print(f"  {k:<20} max={v.max_context_tokens:,} tokens")
        sys.exit(0)
    if len(args) < 2:
        print("Erreur : donne un modèle et un nombre de tokens.")
        sys.exit(1)
    try:
        result = EgoProfiler(args[0]).profile(int(args[1]))
        print(result.summary())
    except ValueError as e:
        print(f"Erreur : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
