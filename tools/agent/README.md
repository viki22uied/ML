# Notebook Submission Checker

A personal agent that catches notebook problems before a reviewer does. Spec: [`submission/personal_agent_spec.md`](../../submission/personal_agent_spec.md).

## What it does and for whom

For me (the repo owner), before I submit a weekly ML notebook: re-runs it end-to-end on a scratch copy, checks its trailing self-check list against what the notebook *actually* produced (not just the checkbox label), flags leftover debug code or hardcoded paths via `git diff`, and reports pass/fail per item. It never edits the real notebook and never runs a git write command.

## Setup

1. Clone this repo and install `requirements.txt`.
2. Make sure `jupyter nbconvert` is on your PATH (already covered by the repo's requirements).
3. Run it from the repo root:

```
python scripts/notebook_checker.py work/notebooks/w05_model.ipynb
```

No API keys, no network access, no extra accounts — it only touches local files.

## Usage example

```
$ python scripts/notebook_checker.py work/notebooks/w05_model.ipynb
[OK]   Notebook executed cleanly end-to-end.
[OK]   All self-check items are marked done and match real cell output.
```

If a dependency file the notebook expects is missing:

```
[FAIL] Missing dependency file: ../outputs/baseline_action_score.csv
       The notebook expects this file to already exist (usually written by
       an earlier weekly notebook/script). Generate it first, then re-run
       this check.
```

## Architecture sketch

```
notebook path
     |
     v
copy to scratch dir (never touch the original)
     |
     v
jupyter nbconvert --execute  --> error? report exact cell + traceback, stop
     |
     v
parse trailing self-check markdown cell
     |
     v
for each checkbox: verify against real cell OUTPUT, not just the label
     |
     v
git diff on the real notebook path --> flag debug prints / hardcoded paths
     |
     v
print pass/fail report
```

## Eval results (real runs, see `BUILD_LOG.md` for full transcripts)

| Case | Result |
|---|---|
| Clean pass (`work/notebooks/w05_model.ipynb`) | `[OK]` on execution and every self-check item |
| Missing dependency file | Caught unforced on the real repo, clear message instead of a raw traceback |
| Execution error (synthetic notebook) | Reported the exact failing cell and traceback, did not guess a fix |
| Checkbox lying (synthetic notebook) | Flagged a checked item with no matching evidence in cell outputs |

## Limitations

- Read-only/scratch-only by design — it will never fix a broken notebook, only report what's broken.
- Needs a Hugging Face token to fully re-run notebooks that pull the gated warehouse dataset (w04/w05); everything else works without one.
- Single-user tool, not built for concurrent use on the same notebook.
