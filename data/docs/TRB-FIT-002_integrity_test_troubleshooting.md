---
doc_id: TRB-FIT-002
title: Troubleshooting Integrity Test Failures
version: 1.4
status: fictional training document
---
# Common causes of high diffusion flow
| Pattern | Likely cause | What to check |
|---|---|---|
| First attempt fails, passes after re-wetting | Incomplete wetting (before Pre-IT or before PUPSIT) | Wetting time of that test, wetting method, crew |
| Fails on one cart across many filter lots | Cart leak (seals, fittings) or cart hardware | Cart leak test, seal condition, recent maintenance |
| Fails on several carts using the same filter lot | Filter lot defect | Filter lot, supplier certificate, incoming inspection |
| Pre-IT normal but PUPSIT high | Damage during sterilization | Autoclave cycle record: temperature, hold time |
| Readings slowly decreasing on one cart | Transducer drift (risk: real failures masked) | Calibration status |
| Small rise on all carts of one line | Room temperature change | Room conditions log |

# Notes
- Marginal failures (just above the limit) are often caused by test conditions, not a defective filter.
- Pressure that drops during the stabilization step points to a gas leak in the cart or connections.
- Always compare against the cart's own history; carts differ slightly from each other.
