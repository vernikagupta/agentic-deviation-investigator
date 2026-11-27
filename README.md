# Agentic Deviation Investigator

An agentic AI system that detects and investigates deviations on a sterile prefilled-syringe fill line:
it monitors filter integrity tests and line stations, detects anomalies, and runs a multi-agent root cause
investigation across historian, MES, ERP, maintenance, autoclave and quality records, with a human
approving the conclusion.

Independent project. All data is synthetic and fictional.

## Status
- [x] Synthetic dataset with planted scenarios and answer key (`datagen/`, `data/`)
- [ ] Ingestion and data quality
- [ ] Anomaly detection per station
- [ ] Agent investigation (tools, orchestration, multi-hop, human approval)
- [ ] Sessions, context engineering, caching, prompt injection defense
- [ ] Evaluation in CI, tracing, API, AWS deployment

## Quick start
```bash
pip install -r requirements.txt
python -m datagen.generate     # regenerate data/ (deterministic)
pytest tests                   # dataset acceptance tests
```

See `data/README.md` for the data dictionary and `DECISIONS.md` for design decisions.
