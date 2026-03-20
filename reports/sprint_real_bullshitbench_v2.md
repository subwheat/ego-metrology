# EGO Metrology — BullshitBench Real Run

**Benchmark :** `bullshitbench_v2`  
**Date :** 2026-03-20  
**Schema :** `reporting.v1`  

## Executive Summary

- **Runs total :** 15
- **Policies :** 1
- **Regret records :** 0
- **Recommended policy :** `single_pass`
- **Best quality policy :** `single_pass`
- **Lowest cost policy :** `single_pass`
- **Lowest regret policy :** `single_pass`

## Policy Comparison

| policy_id | runs | pass_rate | mean_quality | mean_cost | mean_regret | oracle_match |
|-----------|------|-----------|--------------|-----------|-------------|--------------|
| `single_pass` ✓ | 15 | 0.47 | 1.27 | 304.87 | 19.62 | 1.00 |

## Recommendation

**Default policy : `single_pass`**

Highest quality pass rate with best overall tradeoff (pass rate 47%, mean regret 19.6, mean cost 304.9).

_Ranking rule : (1) highest pass rate, (2) lowest mean regret, (3) lowest mean cost, (4) lexicographic policy_id._

## Limits

- Single benchmark (`bullshitbench_v2`)
- `cost_dyn` v1 is a token+latency proxy, not a real provider cost
- `routing_regret` not computable where `cost_dyn` or oracle is missing
- `single_pass_verify` and `cascade_small_to_large` not yet fully executable
