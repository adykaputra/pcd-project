# FYP Privacy Firewall Blueprint

## Project Positioning

This project is no longer just a "redaction script." It is now an **LLM Privacy Firewall**:

1. Detects PII in user prompts
2. Replaces sensitive values with deterministic pseudonym tokens
3. Stores original values in an encrypted vault
4. Sends only tokenized prompts to LLM providers
5. Allows controlled admin-only detokenization for legal/audit workflows
6. Applies a risk/confidence policy engine before model forwarding
7. Exposes an adversarial benchmark endpoint for measurable privacy evaluation

---

## Signature Component: Reversible Privacy Vault

### Why this matters

Most redaction systems permanently destroy context with placeholders like `[REDACTED_EMAIL]`.  
This project adds a better privacy pattern:

- `ali@example.com` -> `[EMAIL_A1B2C3D4E5F6]`
- `012-3456789` -> `[PHONE_9F8E7D6C5B4A]`

The mapping is deterministic (same input -> same token) for context continuity, while raw PII is never sent to the model.

### Security properties

- Raw PII is stored encrypted at rest in `data/pii_vault.db`
- Token IDs are generated from keyed HMAC-based hashes
- Ciphertext integrity is verified before decryption
- Access to detokenization is restricted to admin-authenticated requests

---

## Request Pipeline (Runtime)

### `/generate` flow

1. Accept prompt (`prompt` or legacy `sanitized_prompt`)
2. Run tokenization (`tokenize_prompt_for_llm`)
3. Reject if core PII still remains (fail-safe)
4. Send tokenized prompt to LLM adapter
5. Record auditable security events and tokenization counts
6. Evaluate risk score + confidence and apply policy action (`allow` / `challenge` / `block`)

### `/detokenize` flow (admin-only)

1. Require admin JWT / role
2. Resolve tokens using vault
3. Return reconstructed prompt for compliance use-cases
4. Log `PII_DETOKENIZED` audit event

### `/privacy/benchmark` flow (admin-only)

1. Run a curated adversarial suite (explicit + obfuscated PII)
2. Measure leak-rate, utility proxy score, latency, and policy-action distribution
3. Return per-case traces for explainable demo and validation

---

## Novelty and FYP Value

This architecture contributes beyond common coursework by combining:

- **Privacy-preserving NLP gateway design**
- **Deterministic pseudonymization**
- **Reversible secure vault workflows**
- **RBAC-governed re-identification**
- **Tamper-evident audit logging**
- **Risk-based policy enforcement with confidence scoring**
- **Red-team style benchmark metrics**

This gives a strong "systems + security + AI" story for viva/demo.

---

## Suggested Demo Script

1. Submit prompt with name/email/phone to `/generate`
2. Show adapter receives only tokenized content
3. Show model response quality retained due stable tokens
4. Use admin token on `/detokenize` to recover original text
5. Show audit dashboard events (`PII_TOKENIZED`, `PII_DETOKENIZED`, `SECURITY_DENIED`)

---

## Next Upgrades to Reach "Research-Grade"

1. Add real NER model (spaCy/transformer) to replace heuristic contextual detection
2. Tune scoring with calibrated thresholds from empirical benchmark datasets
3. Add key rotation + external KMS integration for vault keys
4. Add retrieval-safe memory policies for multi-turn chats
5. Add evaluator comparing utility impact vs baseline redaction systems
