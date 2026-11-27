# Agentic Deviation Investigator

An agentic AI system that detects and investigates deviations on a sterile prefilled-syringe fill line:
it monitors filter integrity tests and line stations, detects anomalies, and runs a multi-agent root cause
investigation across historian, MES, ERP, maintenance, autoclave and quality records, with a human
approving the conclusion.

Independent project. All data is synthetic and fictional.

## Status
- [x] Synthetic dataset v2: 2 years of daily drops from 9 source systems plus reference data and SOPs,
  planted scenarios, answer key
- [ ] Ingestion and data quality
- [ ] Anomaly detection per station
- [ ] Agent investigation (tools, orchestration, multi-hop, human approval)
- [ ] Sessions, context engineering, caching, prompt injection defense
- [ ] Evaluation in CI, tracing, API, AWS deployment

## Quick start
```bash
pip install -r requirements.txt
python -m datagen.generate     # generate data/ (~1 min, deterministic, not committed)
pytest tests                   # dataset acceptance tests
```

See `PROBLEM_STATEMENT.md` for the problem being solved, `DOMAIN_NOTES.md` for the process,
`DATA_OVERVIEW.md` for systems and data delivery, `data/README.md` for the data dictionary and `DECISIONS.md` for design decisions.
