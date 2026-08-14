# Agent Spec: Notebook Submission Checker

## Job to be done
Before I submit a weekly ML notebook (like w05_model.ipynb) to the FlyRank internship repo, I want an agent that re-runs the notebook end-to-end, checks it against that week's self-check list, and tells me exactly what's missing or broken — before a reviewer finds it. Right now I catch these issues manually, late, and inconsistently.

## User and usage frequency
Just me (Vignesh Kumar, ML track intern). Used once per week, right before each weekly notebook submission — roughly 8-10 more times over the remainder of the program. Ad hoc reruns whenever I significantly edit a notebook.

## Tools and data needed, with access plan
- **Filesystem read/write** on my local `ML-main` repo folder (`work/notebooks/`, `work/outputs/`) — already have full local access, no new permission needed.
- **Jupyter/nbconvert execution** (`jupyter nbconvert --to notebook --execute`) — already installed locally, agent just needs shell access to run it in a scratch copy so it never corrupts my real notebook if execution fails partway.
- **Git** (`git diff`, `git log`) — read-only, to confirm the notebook's outputs match what's about to be committed, and that no stray debug cells got left in.
- **The weekly self-check list** — each notebook already ends with a markdown self-check cell (checkboxes); agent reads that cell's text directly, no external data source needed.
- No internet/API access required — this agent only touches local files.

## Draft instructions
"You are a submission-readiness checker for a weekly ML notebook.
1. Copy the target notebook to a scratch path.
2. Execute it end-to-end with `jupyter nbconvert --execute`. If it errors, stop and report the exact cell and traceback — do not attempt to fix the notebook yourself.
3. If it runs clean, open the notebook and find the final self-check markdown cell. List every checkbox item.
4. For each checkbox, check the actual notebook contents (not just the label) to verify it's really satisfied — e.g. if a box says 'model comparison table present,' confirm a DataFrame with the right columns actually renders in the output, not just that a cell exists.
5. Run `git diff` on the notebook path and flag any leftover debug/print cells, hardcoded absolute paths, or commented-out code blocks.
6. Output a short pass/fail report: what's confirmed done, what's missing, and the exact cell number for anything that needs fixing.
Never edit the real notebook. Never commit or push anything. Only read, run in scratch, and report."

## Five eval cases
1. **Clean pass**: a finished, correct notebook (like the actual w05_model.ipynb) → agent reports all self-check items pass, no diff issues, ready to submit.
2. **Execution error**: notebook has a cell that throws (e.g., wrong column name after a rename) → agent reports the exact failing cell number and traceback, does not guess a fix.
3. **Checkbox lying**: self-check cell claims "model comparison table present" but the actual comparison cell was deleted or never ran → agent catches the mismatch and flags that specific box as unmet, not just trusts the label.
4. **Leftover debug code**: notebook runs fine but has a stray `print(df.head(50))` or a hardcoded `C:\Users\...` path left in from local testing → agent flags it in the diff-review step without blocking on it (warning, not failure).
5. **Missing input file**: notebook references `../outputs/w05_join_fields.csv` but the file isn't present in the scratch copy's expected relative location → agent reports "missing dependency file" clearly, rather than a confusing raw `FileNotFoundError` traceback dump.

## Risks and guardrails
- **Must confirm before acting**: nothing — this agent is read-only/scratch-only by design, so no destructive step needs a confirmation gate.
- **Must never do**: never edit the real notebook file in place; never run `git commit`, `git push`, or any git write command; never delete files; never touch anything outside the scratch copy and the read-only `git diff`/`git log` checks.
- **Guardrail on execution**: always operate on a copy, never the original, so a bad `nbconvert --execute` run (which can partially overwrite an in-place notebook on crash) can never corrupt real work.
- **Guardrail on scope**: if asked to "just fix it," the agent should refuse and instead report what's broken — fixing modeling logic requires my judgment, not the agent's.

## Platform choice and justification
**Claude Project with filesystem/shell access (via Claude Code or Cowork with a connected local folder)**, rather than an n8n workflow or custom GPT.

Justification: this task needs real code execution (`jupyter nbconvert`) and real git introspection on my actual local repo — an n8n workflow would need a custom code-execution node and file-system credentials that add setup overhead for a single-user, once-a-week tool, and a custom GPT can't execute local shell commands or read my local filesystem at all. A Claude Project/Cowork session with local folder access already gives direct shell + filesystem access with zero extra infrastructure, and I'm already using this exact setup for my other coursework, so there's no new tool to learn or maintain.
