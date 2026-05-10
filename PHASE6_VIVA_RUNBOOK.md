# Phase 6 Viva Runbook

## 1) Setup
```bash
pip install -r requirements.txt
python3 -m pytest -q
```

Optional NER backends:
```bash
# spaCy
pip install spacy
python -m spacy download en_core_web_sm
export PRIVACY_NER_BACKEND=spacy

# transformer
pip install transformers torch
export PRIVACY_NER_BACKEND=transformer
export PRIVACY_NER_TRANSFORMER_MODEL=dslim/bert-base-NER
```

## 2) Start App
```bash
flask --app app run --host 0.0.0.0 --port 5000
```

## 3) Authentication
```bash
curl -s -X POST http://localhost:5000/login -H 'Content-Type: application/json' -d '{"password":"admin-pass"}'
```

## 4) Core Demo Sequence
1. `/generate` with clean prompt
2. `/generate` with explicit PII
3. `/generate` with obfuscated PII
4. `/generate` with exfiltration intent
5. `/detokenize` with admin token

Reference scenarios: `PHASE6_DEMO_SCENARIOS.md`

## 5) Governance Demo Sequence
1. `GET /privacy/benchmark?dataset_version=v2&split=all`
2. `GET /privacy/benchmark?dataset_version=v2&mode=cross_split&persist=1`
3. `GET /privacy/calibrate?dataset_version=v2&split=validation`
4. `GET /privacy/autotune?hours=168&min_samples=10`
5. `GET /privacy/benchmark/history?limit=20`
6. Open `/audit/dashboard`

## 6) Reproducibility Artifacts
```bash
python3 scripts/run_phase6_evaluation.py
```
Outputs:
- `reports/phase6/phase6_evaluation.json`
- `reports/phase6/phase6_evaluation.md`

## 7) CI Gate Check (local)
```bash
python3 scripts/check_benchmark_gate.py --dataset-version v2 --split all
```
