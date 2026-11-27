---
doc_id: SOP-FIT-001
title: Filter Integrity Testing on Integrity Test Carts
version: 3.0
status: fictional training document
---
# Purpose
Define how sterilizing-grade filter assemblies are integrity tested before and after use.

# Test sequence per batch
1. Build the single-use filter assembly and connect it to the integrity test cart.
2. Wet the membrane with water for injection. Minimum wetting time: 60 s.
3. Run the pre-use integrity test (Pre-IT, diffusion method). Limit: <= 1.6 mL/min.
4. Sterilize the assembly in the autoclave (121-124 C, minimum 30 min hold).
5. Run PUPSIT (pre-use post-sterilization integrity test). Limit: <= 4.2 mL/min.
6. Use the assembly for filtration during the batch.
7. After the batch, run the post-use integrity test. Limit: <= 4.5 mL/min.

# Test pressure
Diffusion tests are run at 2500 mbar. The test recipe steps are recorded by the cart
as StepIndex values. The final diffusion flow is valid at StepIndex 1300 (test complete).

# Failed test
- A failed test may be repeated up to 2 more times (3 attempts in total).
- Before repeating: check connections, check wetting time, re-wet if wetting was short.
- If all attempts fail, the filter assembly is rejected, a deviation is raised, and a new assembly is built.
- A test that aborts (StepIndex 9999) is not a result. The cart reports flow 0. Repeat the test.
