# Problem Statement

Fictional plant, synthetic data. Based on a discovery interview with the process engineer responsible for
the three prefilled-syringe fill lines.

## Context
Each line runs batches through filter preparation (build, wet, Pre-IT, autoclave, re-wet, PUPSIT),
filling (Tyvek removal, rotary filler, vacuum stoppering) and a post-use filter integrity test.
A failed test is repeated up to 3 times. If all attempts fail, a deviation is opened in QMS and must be
investigated.

## Problem 1: problems are detected too late
- Action is taken only when a test fails all 3 attempts. By then, the cause has often been building for weeks.
- Slow drifts inside the limit are not trended. Example: cart seal wear makes PUPSIT flow creep up batch
  after batch until a test fails.
- Station data (fill weight per needle, stoppering vacuum, Tyvek removal alarms) is checked one value at a
  time against limits, not trended.
- A drifting sensor can make results look better than they are. A filter that should fail can pass.

## Problem 2: investigations are slow and often start in the wrong direction
- One investigation takes 2 to 6 weeks. The GMP expectation is about 30 days.
- Most of the time is spent collecting data from 8 to 9 systems: historian, MES, ERP, QC, autoclave,
  CMMS, QMS, line data and room conditions.
- The systems do not join cleanly:
  - Historian test results have no batch ID. They are matched to batches by time.
  - Equipment names are written in several ways.
  - CMMS uses local time. The other systems use UTC.
  - A historian upgrade renamed columns and tags.
- The first assessment is often wrong. "Bad filter lot" is the usual first guess, because lots change often.
- Several things change at the same time (new lot, new crew, maintenance work). Ruling causes out takes as
  long as finding the real cause.
- Past cases are not reused. A closed deviation with the same failure on another cart exists in QMS, but
  nobody searches it.

## What the users need
1. **Early warning:** detect a trend or shift before a test fails.
2. **Investigation support:** when a failure happens, one place that:
   - collects evidence from all systems,
   - uses only data that was available at the time of the investigation,
   - proposes likely root causes with the supporting evidence,
   - states which causes were ruled out and why,
   - points to similar past cases.
3. **Human approval:** a person approves the conclusion. QA signs, not the system.

## Success measures (draft, to confirm with the business owner)
- The correct root cause is in the system's top suggestions for planted events.
- Drifts are flagged before the first failed test.
- Red herrings (coincidental changes) are ruled out with evidence.
- Every conclusion cites the source records it is based on.
