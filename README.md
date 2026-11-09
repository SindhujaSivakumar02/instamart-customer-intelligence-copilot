# Instamart Customer Intelligence & Support Copilot

## Overview

This project implements an offline customer intelligence and support copilot using synthetic Instamart data. It covers data cleaning, customer segmentation, lapse-risk scoring, support ticket triage, policy retrieval and a tool-using refund support agent.

All monetary values are in INR. The project uses local data and an offline mock LLM; no paid API is required.

## Reproduce

Run these commands from the project root in PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python generate_data.py
python scripts/audit_data.py
python scripts/part_a.py
python scripts/part_b.py
python scripts/part_c.py
python scripts/part_d.py
```

The scripts generate the clean datasets, SQLite database and Part B, C and D output files.

## Part A

Raw customer, product and order data were cleaned and exported to `data/clean/`. The cleaned tables were also loaded into `data/instamart.db`.

Cleaning includes city and gender normalization, age validation and imputation, duplicate removal, latest-order selection, numeric amount conversion, missing amount reconstruction and delivery-time handling.

Seven analytical SQL queries are available in `sql/queries.sql`.

## Part B

Customer RFM metrics were calculated for 1,175 customers. The lapse cohort contains 1,156 customers, including 443 labelled as lapsed.

The current implementation uses transparent rule-based segmentation and a heuristic lapse-risk score. It is a functional fallback and **does not implement the requested KMeans clustering, Logistic Regression or Random Forest training and evaluation**. The saved `lapse_model.joblib` contains model metadata for this heuristic, not a trained scikit-learn estimator.

The retention list contains up to ten Premium customers ranked by the heuristic score. It is illustrative and should not be treated as a validated prediction.

## Part C

A total of 164 support tickets were processed. Empty and long tickets were skipped for model processing. Email addresses, phone numbers and order IDs were redacted before classification.

The offline mock LLM was used with zero-shot and few-shot prompts. Responses were validated as JSON or classified using a keyword fallback. Invalid outputs were routed for human review.

Generated files:
- `outputs/triage_results.csv`
- `outputs/triage_budget_demo.csv`

The few-shot run used 10,960 tokens and recovered from 19 transient retries.

## Part D

Policy documents were divided into overlapping text chunks and indexed for TF-IDF retrieval. The policy assistant retrieves relevant context and answers using the offline mock LLM.

A tool-using agent supports order lookup, policy search, refund calculation, refund issuance and human escalation. It records agent runs, refund ledger entries and resumable state checkpoints.

Generated files:
- `outputs/agent_runs.jsonl`
- `outputs/refund_ledger.jsonl`
- `state/`

Seven agent scenarios were executed, including a maximum-iteration fallback scenario.

## Limitations and Next Steps

- The current Part B implementation is rule-based and should be extended with the required trained clustering and classification models.
- Model evaluation, cross-validation, oversampling and feature-importance analysis remain future work.
- The mock LLM is an offline simulation and does not represent the quality or behaviour of a hosted language model.
- TF-IDF retrieval has limitations when relevant policy information is split across chunk boundaries.
- The retention list is illustrative and requires validation before real-world use.
- All data is synthetic and intended only for educational demonstration.
