# Phase 6 Architecture Slides Outline

## Slide 1 - Title
- **LLM Privacy Firewall: From Redaction to Governance**
- Team, course, supervisor

## Slide 2 - Problem
- Raw user prompts may contain PII
- Model providers and logs introduce exposure risk
- Need enforceable, measurable privacy boundary

## Slide 3 - System Overview
- Input -> Tokenization Vault -> Risk Engine -> Policy Action -> LLM
- Admin-only detokenization path
- Audit and benchmark governance loop

## Slide 4 - Privacy Vault
- Deterministic pseudonym tokens
- Encrypted mapping store
- Controlled re-identification

## Slide 5 - Risk & Policy Engine
- Signals: core/contextual/NER/obfuscation/intent/residual
- Actions: allow / challenge / block
- Explainable reasons + confidence

## Slide 6 - NER Layer Evolution
- Fallback rules
- spaCy backend
- Transformer backend option
- Multilingual Malay-English handling

## Slide 7 - Benchmark Science
- Versioned datasets (`v1`, `v2`)
- Split-wise evaluation (train/validation/test)
- Metrics: leak-rate, detection-rate, utility, latency, action accuracy

## Slide 8 - Calibration & Autotune
- Benchmark-driven threshold search
- Audit-telemetry recommendations
- Persisted threshold config

## Slide 9 - Observability
- Benchmark history store
- Dashboard trend section
- CI benchmark gate

## Slide 10 - Security Controls
- RBAC for detokenization/admin endpoints
- Tamper-evident audit logs
- Policy-denied path behavior

## Slide 11 - Results Snapshot
- Latest benchmark metrics
- Cross-split table
- Gate pass/fail summary

## Slide 12 - Limitations & Future Work
- Multilingual model quality variability
- Key management hardening with KMS
- Real-world dataset curation and adversarial expansion
