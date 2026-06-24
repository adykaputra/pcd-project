# Phase 6 Evaluation Report

## 1. Executive Summary
- Project objective: enforce pre-LLM PII protection by tokenizing/redacting user-sensitive data before model dispatch, with measurable privacy and governance metrics.
- Key outcomes:
  - Core PII leak rate achieved at 0.000 on dataset v2 (all split).
  - PII detection rate 0.833, utility score 0.876, latency 2.294 ms.
  - End-to-end evaluation artifacts generated (`reports/phase6/phase6_evaluation.json` and `.md`).
- Final benchmark gate status: **PASS**.

## 2. System Version
- Commit hash: `b369593`
- Dataset version(s): available `v1`, `v2`, `v3`; evaluated on `v2`.
- NER backend used: `fallback` (rule-based), with runtime configured as `PRIVACY_NER_BACKEND=auto`.
- Threshold config source: calibration on `v2` validation set plus autotune recommendation (`benchmark_fallback_insufficient_audit_samples` when audit samples are insufficient).

## 3. Experimental Setup
- Environment details: Linux host, Python/Flask service, SQLite-backed vault and audit stores, local scripted benchmark run.
- Commands executed:
  - `python3 scripts/run_phase6_evaluation.py`
  - (validation) `python3 -c "from app.privacy_ner import detect_named_entities; print(detect_named_entities('Ali from Kuala Lumpur'))"`
- Endpoints exercised (project runbook reference):
  - `/generate`
  - `/detokenize`
  - `/privacy/benchmark`
  - `/privacy/calibrate`
  - `/privacy/autotune`
  - `/privacy/benchmark/history`
  - `/audit/dashboard`

## 4. Benchmark Results
### 4.1 Overall
- Leak rate: `0.000`
- PII detection rate: `0.833`
- Expected action accuracy: `0.333`
- Utility score: `0.876`
- Latency: `2.294 ms`

### 4.2 Cross-split Results
| Split | Cases | Leak Rate | Detection Rate | Action Accuracy | Utility | Latency |
|------|-------|-----------|----------------|-----------------|---------|---------|
| train | 3 | 0.000 | 1.000 | 1.000 | 0.898 | 1.724 ms |
| validation | 3 | 0.000 | 0.667 | 0.000 | 0.825 | 1.083 ms |
| test | 3 | 0.000 | 1.000 | 0.000 | 0.904 | 1.758 ms |

### 4.3 Language Distribution
- en: `2`
- ms: `4`
- ms-en: `3`

## 5. Policy Analysis
- Challenge threshold: `25`
- Block threshold: `60`
- Calibration objective cost: `3.5` (v2 validation)
- Autotune recommendation summary: retained threshold profile at challenge `25` / block `60`; source was benchmark fallback due insufficient recent audit samples (`sample_count=0`).

## 6. Attack Scenario Outcomes
| Scenario | Input Type | Expected | Actual | Notes |
|----------|------------|----------|--------|-------|
| A | Clean prompt | Allow | Allow | Matches expected; no tokenization required. |
| B | Explicit PII | Tokenize + Allow/Challenge | Tokenize + Allow | PII transformed into vault tokens before dispatch. |
| C | Obfuscated PII | Challenge | Allow | Detection occurred in partial cases; policy strictness needs tuning. |
| D | Exfiltration intent | Block/Challenge | Allow | Residual policy gap for intent-level enforcement in current threshold profile. |
| E | Admin detokenization | Controlled restore | Controlled restore (admin-only) | Re-identification remains gated behind privileged route. |

## 7. CI Gate Result
- Gate command: `python3 scripts/check_benchmark_gate.py --dataset-version v2 --split all`
- Thresholds:
  - max leak rate `<= 0.05`
  - min utility score `>= 0.75`
  - max latency `<= 100.0 ms`
  - min detection rate `>= 0.6`
  - min expected action accuracy `>= 0.3`
- Pass/Fail: **PASS**
- Failed checks (if any): none.

## 8. Security Discussion
- Threats mitigated:
  - direct raw-PII dispatch to LLM providers,
  - unauthorized viewing through admin-side redacted evidence workflow,
  - uncontrolled data persistence via retention and purge controls.
- Residual risks:
  - policy-action strictness under obfuscation and exfiltration intent still below target behavior,
  - fallback NER may miss sophisticated entity forms compared with full transformer/spaCy stacks.
- Assumptions and constraints:
  - benchmark dataset scope is limited (9 v2 cases for this run),
  - results depend on configured thresholds and current detector backend,
  - stronger adversarial coverage requires expanded corpus and continuous telemetry-driven tuning.

## 9. Conclusion
- Final quality assessment: strong privacy baseline (zero leak) with high utility and low latency; governance/policy strictness remains the main improvement area.
- Deployment readiness: suitable for controlled showcase and pilot deployment with current safeguards, audit trails, and reproducible evaluation artifacts.
- Next-step recommendations:
  - improve challenge/block policy for adversarial and exfiltration prompts,
  - expand adversarial dataset and multilingual obfuscation cases,
  - enable higher-capability NER backend (spaCy/transformer) in production profile for stronger recall.
