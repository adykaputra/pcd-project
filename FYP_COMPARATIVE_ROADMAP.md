# FYP Comparative Roadmap: LLM Privacy Firewall

## Problem Statement

How can we reduce customer PII exposure to LLM systems while preserving utility
and response quality under real-world prompt conditions?

## Core Research Objective

Evaluate and compare multiple redaction methods, then design an adaptive
selection strategy that chooses the best method per prompt scenario.

## Methods Compared

1. Basic Regex
2. Microsoft Presidio
3. Keyword + Vault
4. Named Entity Recognition (NER)
5. LLM Validator Guard

## Evaluation Dimensions

- Target recall (PII items removed)
- Core leak rate (residual ID/phone/email after redaction)
- Utility score (prompt preservation proxy)
- Latency (milliseconds)
- Composite score (weighted ranking)

## Dataset Path

- `v1`: baseline prompts
- `v2`: multilingual prompts
- `v3`: comparative prompts with explicit `pii_targets` and adversarial cases

## Adaptive Selector Goal

Given a prompt case, compare all method outputs, compute a composite score, and
select the best method while reporting risk and evidence.

## Deliverables for Viva

- Comparative leaderboard (method ranking by metrics)
- Case-level evidence (adaptive-selected method per scenario)
- Reproducible artifacts (`reports/comparative/*`)
- Demonstration in dashboard (`/privacy/comparison`)
