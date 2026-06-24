# Phase 6 Evaluation Report Template

## 1. Executive Summary
- Project objective: To prevent raw PII from reaching LLM providers by enforcing tokenization, risk scoring, and policy control at runtime.
- Key outcomes: Core PII leak rate 0.000; detection rate 0.833; utility score 0.876; latency 2.294 ms; reproducible evaluation artifacts generated.
- Final benchmark gate status: PASS.

## 2. System Version
- Commit hash: b369593
- Dataset version(s): Available v1, v2, v3; evaluated on v2.
- NER backend used: fallback (rule-based) under auto backend selection.
- Threshold config source: Validation calibration (v2) and autotune recommendation fallback (insufficient recent audit samples).

## 3. Experimental Setup
- Environment details: Linux, Flask application runtime, SQLite audit/vault persistence, local benchmark execution.
- Commands executed: `python3 scripts/run_phase6_evaluation.py`; validation probe for named-entity detection backend.
- Endpoints exercised: /generate, /detokenize, /privacy/benchmark, /privacy/calibrate, /privacy/autotune, /privacy/benchmark/history, /audit/dashboard.

## 4. Benchmark Results
### 4.1 Overall
- Leak rate: 0.000
- PII detection rate: 0.833
- Expected action accuracy: 0.333
- Utility score: 0.876
- Latency: 2.294 ms

### 4.2 Cross-split Results
| Split | Cases | Leak Rate | Detection Rate | Action Accuracy | Utility | Latency |
|------|-------|-----------|----------------|-----------------|---------|---------|
| train | 3 | 0.000 | 1.000 | 1.000 | 0.898 | 1.724 ms |
| validation | 3 | 0.000 | 0.667 | 0.000 | 0.825 | 1.083 ms |
| test | 3 | 0.000 | 1.000 | 0.000 | 0.904 | 1.758 ms |

### 4.3 Language Distribution
- en: 2
- ms: 4
- ms-en: 3

## 5. Policy Analysis
- Challenge threshold: 25
- Block threshold: 60
- Calibration objective cost: 3.5
- Autotune recommendation summary: Retained challenge/block profile (25/60); source indicates benchmark fallback due sample_count=0.

## 6. Attack Scenario Outcomes
| Scenario | Input Type | Expected | Actual | Notes |
|----------|------------|----------|--------|-------|
| A | Clean prompt | Allow | Allow | Expected low-risk behavior confirmed. |
| B | Explicit PII | Tokenize + Allow/Challenge | Tokenize + Allow | Sensitive fields replaced with vault tokens before dispatch. |
| C | Obfuscated PII | Challenge | Allow | Indicates policy strictness gap under obfuscated formats. |
| D | Exfiltration intent | Block/Challenge | Allow | Indicates intent-governance gap requiring threshold/rule tuning. |
| E | Admin detokenization | Controlled restore | Controlled restore | Privileged restoration path remains access-controlled. |

## 7. CI Gate Result
- Gate command: `python3 scripts/check_benchmark_gate.py --dataset-version v2 --split all`
- Thresholds: leak<=0.05, utility>=0.75, latency<=100.0 ms, detection>=0.6, expected-action-accuracy>=0.3.
- Pass/Fail: PASS
- Failed checks (if any): None.

## 8. Security Discussion
- Threats mitigated: Raw PII forwarding, unauthorized data visibility, and uncontrolled retention via purge/retention controls.
- Residual risks: Obfuscated and exfiltration-intent prompts are not yet consistently challenged/blocked.
- Assumptions and constraints: Small benchmark size (9 cases), fallback NER limitations, and dependence on threshold configuration.

## 9. Conclusion
- Final quality assessment: Strong privacy baseline with zero measured leak and high utility, but policy strictness remains the main improvement target.
- Deployment readiness: Suitable for controlled showcase deployment with auditable evidence and reproducible metrics.
- Next-step recommendations: Tighten challenge/block policy, expand adversarial multilingual tests, and enable stronger NER backend in production.
