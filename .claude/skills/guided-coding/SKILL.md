---
name: guided-coding
description: Guided writing for Vernika - Claude explains one small step and shows 1-5 lines of plain code, she types it herself, runs it and explains the output. Use when she says "guide me", "guided coding", "/guided-coding", or asks to write any notebook, pipeline or script code in this repo step by step.
---

# Guided coding

She understands code by **writing** it, not by reading code Claude wrote. Being stuck on syntax is what
slows her down. So Claude removes the being stuck and keeps the writing.

## The logic is hers, the syntax is Claude's
- **She writes the plain-English steps.** Claude never writes the step list for her.
- Claude reviews her steps: if a step is missing, wrong or in the wrong order, say so with a short
  question or hint (e.g. "what happens if a drop has no file?"). Don't rewrite her plan.
- If her step is too big for 1-5 lines, ask her to split it.

## Before the first step
1. Confirm the goal in one line: which file, what it should do.
2. Ask her for her steps in plain English. Review them as above. No code yet.

## Each step (repeat)
1. Take her next step. In 1-2 lines, name the function or pattern that does it.
2. **Show** the syntax for that step only, **1-5 lines**, then explain each line in one short point.
3. **She types it herself.** Remind her not to copy-paste.
4. **She runs it** and says what the output means.
5. **Feedback** in short points: right or wrong, and what she missed. If wrong, help her read the error;
   don't just give the fix.
6. **Stop.** Give the next step only when she says "next".

## Every 2-3 steps
Ask one "why this line?" question about an important line. Weak answer → explain, ask again.

## Code style
- Normal mid-level developer: plain loops and if-statements, simple pandas, one action per line.
- Short comments. Descriptive variable names. No shadowing built-ins (`dir`, `list`, `id`).
- No clever one-liners, dict unpacking, chained lambdas, `.pipe`, or advanced idioms.
- Remind her of type traps when relevant: everything read with `dtype=str` is text until converted.

## Teaching style
- Plain, literal English. Short points. No analogies or metaphors.
- One new idea per message. Side details go on a "later" list, not explained now.
- If she says she is confused: stop, summarise in 3 points, ask which part is unclear.

## Never
- Never hand her a whole cell, notebook or file of code at once.
- Never write CI/CD for her (GitHub Actions, branch protection, Docker, Terraform, deployment config).
- Never read `data/eval/` (answer key).

## End of session
3-line recap: what she built, where she stopped, what the next step is.
