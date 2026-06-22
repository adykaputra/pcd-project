# STTZK4993 Academic Project 2 - Field Test Report (Draft)

**Project Title:** Integrating Machine Unlearning for Data Privacy Within Defect Liability Period (DLP): Ethical and Compliant Legaltech Systems  
**System Name:** LLM Privacy Firewall (DLP-Oriented Legaltech Assistant)  
**Student ID / Name:** `<fill in>`  
**Date of Test:** 2026-06-22  
**Test Environment:** Linux (Docker + Flask), SQLite vault/audit store, Ollama/mock-compatible runtime

---

## 1. Overview of the System / Application

This project implements a privacy-first LLM gateway for legaltech use cases under a Defect Liability Period (DLP) workflow. The core objective is to prevent the language model from receiving raw personally identifiable information (PII), while preserving response quality for users.

The system architecture places a privacy firewall between users and the LLM:

1. User submits prompt (optionally with image/document attachment).
2. Firewall detects sensitive entities (name, phone, email, ID, location, organization, etc.).
3. Sensitive spans are replaced with deterministic vault tokens (for example `[EMAIL_xxx]`, `[PHONE_xxx]`).
4. Risk policy evaluates the prompt and applies an action: `allow`, `challenge`, or `block`.
5. Only tokenized/redacted content is dispatched to the model adapter (Ollama or fallback).
6. Security/audit evidence is logged, and privileged detokenization is controlled on the admin side.

This design demonstrates that privacy protection is enforced as a runtime control, not merely a user guideline.

---

## 2. Evaluation Method

### 2.1 Evaluation Objective

The field test evaluates:

- **Privacy effectiveness** (PII leakage prevention and detection rate),
- **Governance correctness** (policy action alignment),
- **Utility preservation** (how useful responses remain),
- **Operational feasibility** (latency and reproducibility for showcase/demo use).

### 2.2 Dataset and Protocol

- Benchmark dataset version: **v2**
- Total cases: **9**
- PII cases: **6**
- Language distribution:
  - English (`en`): **2**
  - Malay (`ms`): **4**
  - Mixed (`ms-en`): **3**

Cross-split protocol:

- **Train:** 3 cases
- **Validation:** 3 cases
- **Test:** 3 cases

### 2.3 Metrics Used

- Core PII leak rate
- PII detection rate
- Expected action accuracy (allow/challenge/block match)
- Average utility score
- Average latency (ms)
- CI gate pass/fail against configured thresholds

### 2.4 Reproducibility Commands

```bash
python3 scripts/run_phase6_evaluation.py
```

Artifacts generated:

- `reports/phase6/phase6_evaluation.json`
- `reports/phase6/phase6_evaluation.md`

---

## 3. Results and Findings

### 3.1 Overall Quantitative Results (v2, all split)

- **Core PII leak rate:** **0.000** (0%)
- **PII detection rate:** **0.833** (83.3%)
- **Expected action accuracy:** **0.333** (33.3%)
- **Average utility score:** **0.876** (87.6%)
- **Average latency:** **2.995 ms**
- **Gate status:** **PASS**

### 3.2 Cross-Split Results

| Split | Cases | Detection Rate | Leak Rate | Action Accuracy | Utility | Latency (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Train | 3 | 1.000 | 0.000 | 1.000 | 0.898 | 2.855 |
| Validation | 3 | 0.667 | 0.000 | 0.000 | 0.825 | 2.465 |
| Test | 3 | 1.000 | 0.000 | 0.000 | 0.904 | 2.098 |

### 3.3 Key Findings

1. **No core PII leakage was observed** in benchmark execution (strong privacy outcome).
2. **Detection performance is high but not perfect** (83.3% overall), indicating improvement opportunity for obfuscated/edge PII patterns.
3. **Policy-action accuracy is currently weak** (33.3%), showing a gap between redaction success and risk-action strictness.
4. **Utility remains high** (87.6%), meaning privacy protection did not heavily degrade usable output.
5. **Latency is low** (~3 ms average in benchmark mode), suitable for interactive demo flow.

### 3.4 Calibration / Autotune Snapshot

- Challenge threshold: **25**
- Block threshold: **60**
- Calibration objective cost (validation): **3.5**
- Autotune source: benchmark fallback (insufficient live audit samples at run time)

---

## 4. Implication of the Results

### 4.1 Practical Implications

- The system is **effective as a privacy firewall** because it consistently prevents core PII from being passed through in raw form.
- The project supports legaltech DLP usage by combining **privacy enforcement + auditable governance**, which is stronger than a plain chatbot.

### 4.2 Technical Implications

- Redaction/tokenization layer is mature enough for showcase.
- Risk policy tuning still needs refinement to better separate `allow` vs `challenge/block`, especially for adversarial intent patterns.
- Current benchmarking validates a strong baseline and provides measurable evidence for iterative threshold improvement.

### 4.3 Academic Implications

This work demonstrates a viable direction for "machine unlearning-ready privacy operations" by minimizing exposure before model ingestion and retaining only tokenized traces with retention/purge controls. It contributes a measurable framework (leak/detection/utility/latency/gate) suitable for final-year research evaluation.

---

## 5. Conclusion

The field test confirms that the developed DLP-oriented privacy firewall is functional, reproducible, and evaluation-driven. The strongest result is zero core PII leakage in tested cases, with high utility and low latency. The main improvement area is policy decision strictness on challenge/block actions for higher-risk prompts.

Overall, the system is suitable for FYP showcase as a deployable and measurable privacy engineering solution, with clear next-step work on risk scoring calibration and adversarial handling.

---

## 6. Appendix (Evidence References)

- Main evaluation summary: `reports/phase6/phase6_evaluation.md`
- Full metrics JSON: `reports/phase6/phase6_evaluation.json`
- Demo walkthrough: `PHASE6_VIVA_RUNBOOK.md`
- Scenario definitions: `PHASE6_DEMO_SCENARIOS.md`

