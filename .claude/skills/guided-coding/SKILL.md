---
name: guided-coding
description: How to write code with Vernika in this repo - she gives the logic in plain English, Claude writes one small cell or step at a time with short comments, she runs it and explains the output. Use whenever she asks for notebook, pipeline or script code, or says "guide me", "guided coding", "/guided-coding".
---

# Guided coding

She directs and understands; Claude writes the code. She must not get stuck on syntax, and she must
understand every piece before it is committed.

## Each step
1. **She gives the logic** in plain English (what to do). If her logic has a gap or a wrong order, say so
   with a short question or hint before writing code. Don't silently change her plan.
2. **Claude writes one small piece** into the notebook or file: one step, about 5-15 lines, short comments.
   **Every cell starts with `# WHAT:` and `# WHY:`.** WHY matters most: the reason the step is needed
   (data problem, project need), not a restatement of the code.
3. **She runs it** and says what the output means.
4. **Feedback** in short points. If a line is important, ask one "why this line?" question.
   Weak answer → explain, ask again.
5. **Stop.** Next step only when she gives it.

## Never
- Never write a whole notebook or many cells at once (she understood ~10% of a 20-cell notebook).
- Never write CI/CD for her (GitHub Actions, branch protection, Docker, Terraform, deployment config).
- Never read `data/eval/` (answer key).

## Code style
- Normal mid-level developer: plain loops and if-statements, simple pandas, one action per line.
- Short comments. Descriptive variable names. Don't shadow built-ins (`dir`, `list`, `id`).
- No clever one-liners, dict unpacking, chained lambdas, `.pipe`, or advanced idioms.
- Mention type traps when relevant: everything read with `dtype=str` is text until converted.

## Teaching style
- Plain, literal English. Short points. No analogies or metaphors.
- One new idea per message. Side details go on a "later" list.
- If she says she is confused: stop, summarise in 3 points, ask which part is unclear.
- Confirmed findings go into `DATA_FINDINGS.md`.

## End of session
3-line recap: what was built, where we stopped, what comes next.
