# Phase 6 Evaluation Report Template

## 1. Executive Summary
- Project objective
- Key outcomes
- Final benchmark gate status

## 2. System Version
- Commit hash:
- Dataset version(s):
- NER backend used:
- Threshold config source:

## 3. Experimental Setup
- Environment details
- Commands executed
- Endpoints exercised

## 4. Benchmark Results
### 4.1 Overall
- Leak rate:
- PII detection rate:
- Expected action accuracy:
- Utility score:
- Latency:

### 4.2 Cross-split Results
| Split | Cases | Leak Rate | Detection Rate | Action Accuracy | Utility | Latency |
|------|-------|-----------|----------------|-----------------|---------|---------|
| train |  |  |  |  |  |  |
| validation |  |  |  |  |  |  |
| test |  |  |  |  |  |  |

### 4.3 Language Distribution
- en:
- ms:
- ms-en:

## 5. Policy Analysis
- Challenge threshold:
- Block threshold:
- Calibration objective cost:
- Autotune recommendation summary:

## 6. Attack Scenario Outcomes
| Scenario | Input Type | Expected | Actual | Notes |
|----------|------------|----------|--------|-------|
| A | Clean prompt | Allow |  |  |
| B | Explicit PII | Tokenize + Allow/Challenge |  |  |
| C | Obfuscated PII | Challenge |  |  |
| D | Exfiltration intent | Block/Challenge |  |  |
| E | Admin detokenization | Controlled restore |  |  |

## 7. CI Gate Result
- Gate command:
- Thresholds:
- Pass/Fail:
- Failed checks (if any):

## 8. Security Discussion
- Threats mitigated
- Residual risks
- Assumptions and constraints

## 9. Conclusion
- Final quality assessment
- Deployment readiness
- Next-step recommendations
