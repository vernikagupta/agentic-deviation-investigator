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

## End users
| User | Uses it for | Needs from it |
|---|---|---|
| **Process engineer** (main user) | Receives early warnings and investigation drafts, checks the evidence, edits the draft. | Correct cause, linked evidence, what was ruled out, past cases. |
| **QA specialist** (main user) | Reviews the investigation, approves or rejects the conclusion before the deviation is closed in QMS. | Clear reasoning, sources, audit trail. QA signs, not the system. |
| **Maintenance engineer** | Acts on equipment findings (for example "check the inlet seal on cart B2"). | A specific equipment and check, early enough to plan the work. |
| **Production supervisor / shift lead** | Sees alerts for their line during the shift. | A short alert: what, which equipment, how urgent. |
| **Management** (site quality head, operations head) | Occasionally reviews trends: deviation counts, closure time, repeat failures. | Summary numbers, not details. |

If the process engineer and QA do not trust the system, nobody will use it.

## What the users need
1. **Early warning:** detect a trend or shift before a test fails.
2. **Investigation support:** when a failure happens, one place that:
   - collects evidence from all systems,
   - uses only data that was available at the time of the investigation,
   - proposes likely root causes with the supporting evidence,
   - states which causes were ruled out and why,
   - points to similar past cases.
3. **Human approval:** a person approves the conclusion. QA signs, not the system.

## Acceptance criteria
Agreed with the process engineer. QA may add their own. Items marked **(fixed)** are not negotiable;
the numbers in the others can be adjusted.

### Early detection
1. A slow drift on a cart is flagged before the first failed test, ideally several batches earlier.
2. False alarms: at most about 1 per line per month.
3. Normal changes are not raised as faults (for example, flows rising slightly in spec when the room is warmer).
4. Stations are covered too: fill weight per needle, stoppering vacuum, Tyvek removal alarms.

### Investigation
5. The correct root cause is the first suggestion in most cases and in the top 3 almost always.
6. **(fixed)** Every statement cites its source record: batch, assembly, lot, work order, deviation,
   autoclave cycle.
7. It states which causes were ruled out and why.
8. **(fixed)** It uses only data that existed at the investigation time ("as of").
9. It finds similar past deviations and says how this case is similar or different.
10. If the evidence is not enough, it says so instead of guessing.

### Speed
11. A draft investigation is ready within 1 hour of the trigger.

### Control and compliance (GMP)
12. **(fixed)** Nothing goes into QMS without a person approving it. The person can approve, reject or edit.
13. **(fixed)** Every run is recorded: data used, conclusion, who approved and when (audit trail, data integrity).
14. Bad data from one system does not stop the system. It reports what was missing or bad and continues.
