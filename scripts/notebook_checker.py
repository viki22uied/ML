"""
Notebook Submission Checker
============================
Agent built from the spec in submission/personal_agent_spec.md.

Job: before submitting a weekly ML notebook, re-run it end-to-end on a
scratch copy, verify the self-check list against what the notebook
actually produced (not just the checkbox labels), and flag leftover
debug code or hardcoded paths via git diff. Never touches the real
notebook, never commits or pushes anything.

Usage:
    python notebook_checker.py work/notebooks/w05_model.ipynb
"""

import sys
import os
import re
import shutil
import subprocess
import tempfile
import json


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def warn(msg):
    print(f"[WARN] {msg}")


def ok(msg):
    print(f"[OK]   {msg}")


def make_scratch_copy(notebook_path):
    """Copy the notebook (and its relative outputs dir, if present) to a
    temp scratch directory so nbconvert can never corrupt the original."""
    notebook_path = os.path.abspath(notebook_path)
    if not os.path.exists(notebook_path):
        fail(f"Notebook not found: {notebook_path}")

    repo_root = notebook_path
    # walk up until we find a .git dir, to know the repo boundary
    while repo_root != os.path.dirname(repo_root):
        if os.path.isdir(os.path.join(repo_root, ".git")):
            break
        repo_root = os.path.dirname(repo_root)

    scratch_dir = tempfile.mkdtemp(prefix="nbcheck_")
    # mirror the relative path structure from repo root into scratch,
    # since notebooks often reference ../outputs/*.csv by relative path
    rel_path = os.path.relpath(notebook_path, repo_root)
    scratch_notebook = os.path.join(scratch_dir, rel_path)
    os.makedirs(os.path.dirname(scratch_notebook), exist_ok=True)
    shutil.copy2(notebook_path, scratch_notebook)

    # copy sibling data/output dirs one level up from the notebook (common
    # pattern: work/notebooks/x.ipynb reading ../outputs/y.csv)
    notebook_dir = os.path.dirname(notebook_path)
    parent_dir = os.path.dirname(notebook_dir)
    for candidate in ("outputs", "data"):
        src = os.path.join(parent_dir, candidate)
        if os.path.isdir(src):
            rel_parent = os.path.relpath(parent_dir, repo_root)
            dst = os.path.join(scratch_dir, rel_parent, candidate)
            shutil.copytree(src, dst, dirs_exist_ok=True)

    return scratch_notebook, repo_root, scratch_dir


def execute_notebook(scratch_notebook):
    """Run nbconvert --execute in place on the scratch copy. Returns
    (success, stderr_tail). Tries the 'jupyter' executable on PATH first
    (most reliable across environments where `python -m jupyter` doesn't
    resolve as a module), then falls back to `python -m nbconvert`."""
    candidates = [
        [shutil.which("jupyter") or "jupyter", "nbconvert",
         "--to", "notebook", "--execute", "--inplace", scratch_notebook],
        [sys.executable, "-m", "nbconvert",
         "--to", "notebook", "--execute", "--inplace", scratch_notebook],
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except FileNotFoundError:
            # this candidate isn't installed/on PATH at all — try the next one
            continue
        # the candidate ran (found and executed) — its result is final,
        # whether pass or fail. Don't let a later fallback's unrelated
        # "module not found" error clobber a real execution traceback.
        if result.returncode == 0:
            return True, None
        return False, result.stderr[-4000:]
    return False, "Neither `jupyter nbconvert` nor `python -m nbconvert` is available."


def extract_self_check(scratch_notebook):
    """Find the final markdown cell containing checkbox items
    (- [x] or - [ ]) and return the raw checklist text plus parsed items."""
    with open(scratch_notebook, "r", encoding="utf-8") as f:
        nb = json.load(f)

    checklist_cells = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        text = "".join(cell.get("source", []))
        if re.search(r"- \[[ xX]\]", text):
            checklist_cells.append(text)

    if not checklist_cells:
        return None, []

    last = checklist_cells[-1]
    items = re.findall(r"- \[([ xX])\]\s*(.+)", last)
    return last, items


def verify_items_against_outputs(scratch_notebook, items):
    """Heuristic cross-check: for each checked item, look for corresponding
    evidence in code cell outputs (e.g. a DataFrame, a printed metric).
    This is deliberately conservative — it flags only clear mismatches,
    it doesn't try to fully understand notebook semantics."""
    with open(scratch_notebook, "r", encoding="utf-8") as f:
        nb = json.load(f)

    all_output_text = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        for out in cell.get("outputs", []):
            data = out.get("data", {})
            text = out.get("text", "")
            if isinstance(text, list):
                text = "".join(text)
            all_output_text.append(text)
            if "text/plain" in data:
                tp = data["text/plain"]
                all_output_text.append("".join(tp) if isinstance(tp, list) else tp)

    combined_output = "\n".join(all_output_text).lower()

    findings = []
    for checked, label in items:
        is_checked = checked.lower() == "x"
        if not is_checked:
            continue
        # crude keyword match: pull a few significant words from the label
        # and see if any show up in actual cell output text
        words = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", label)]
        if not words:
            continue
        hits = sum(1 for w in words if w in combined_output)
        coverage = hits / max(len(words), 1)
        if coverage < 0.15:
            findings.append(
                f"Checked item '{label.strip()}' has little/no matching "
                f"evidence in cell outputs (keyword coverage {coverage:.0%}) "
                f"— verify manually."
            )
    return findings


def check_git_diff(repo_root, notebook_path):
    """Read-only git diff on the notebook to flag leftover debug prints or
    hardcoded absolute paths. Never writes or commits anything."""
    rel_path = os.path.relpath(notebook_path, repo_root)
    result = subprocess.run(
        ["git", "-C", repo_root, "diff", "--", rel_path],
        capture_output=True, text=True,
    )
    diff_text = result.stdout

    findings = []
    added_lines = [l for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
    for line in added_lines:
        if re.search(r"print\(\s*df", line, re.IGNORECASE):
            findings.append(f"Possible leftover debug print: {line.strip()[:100]}")
        if re.search(r"[A-Za-z]:\\\\Users\\\\|/home/[a-zA-Z0-9_]+/", line):
            findings.append(f"Possible hardcoded local path: {line.strip()[:100]}")
    return findings


def main():
    if len(sys.argv) != 2:
        print("Usage: python notebook_checker.py <path/to/notebook.ipynb>")
        sys.exit(1)

    target = sys.argv[1]
    print(f"Checking: {target}\n")

    scratch_notebook, repo_root, scratch_dir = make_scratch_copy(target)
    try:
        print("Executing on scratch copy (original file untouched)...")
        success, stderr_tail = execute_notebook(scratch_notebook)
        if not success:
            # nbconvert's tracebacks are ANSI-colored; strip escape codes first
            # so the error text is contiguous and easy to pattern-match.
            plain = re.sub(r"\x1b\[[0-9;]*m", "", stderr_tail or "")
            missing = re.search(
                r"No such file or directory:\s*'([^']+)'",
                plain,
            )
            if missing:
                print(f"\n[FAIL] Missing dependency file: {missing.group(1)}")
                print("       The notebook expects this file to already exist (usually written "
                      "by an earlier weekly notebook/script). Generate it first, then re-run "
                      "this check.")
            else:
                print("\n[FAIL] Notebook execution errored. Traceback tail:\n")
                print(stderr_tail)
            sys.exit(1)
        ok("Notebook executed cleanly end-to-end.")

        checklist_text, items = extract_self_check(scratch_notebook)
        if checklist_text is None:
            warn("No self-check checklist cell found (expected a markdown "
                 "cell with '- [x]' / '- [ ]' items). Skipping checklist verification.")
        else:
            unchecked = [label for checked, label in items if checked.strip().lower() != "x"]
            if unchecked:
                for label in unchecked:
                    warn(f"Self-check item NOT marked done: {label.strip()}")
            else:
                ok(f"All {len(items)} self-check items are marked done.")

            mismatches = verify_items_against_outputs(scratch_notebook, items)
            if mismatches:
                for m in mismatches:
                    warn(m)
            else:
                ok("Checked self-check items have supporting evidence in cell outputs.")

        diff_findings = check_git_diff(repo_root, os.path.abspath(target))
        if diff_findings:
            for f in diff_findings:
                warn(f)
        else:
            ok("No leftover debug prints or hardcoded paths found in the diff.")

        print("\nDone. This report is informational only — nothing was "
              "committed, pushed, or edited in the real notebook.")
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
