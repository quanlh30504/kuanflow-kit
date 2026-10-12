---
work: KF-003-p2-content
status: open (Gate P2)
---
# Questions raised in P2

## Q-29 guard-bash false positives on quoted text (review F1 follow-up)
To stop `bash -c "…"` / `eval "…"` bypasses, guard-bash also scans every quoted word as a command line. A
commit message such as `git commit -m "explain git push origin main"` is therefore blocked. The PKG §18.4
grep sample behaves the same way.
- A. Keep it (safer; the agent rewords the message or the human commits).
- B. Scan nested words only after `bash|sh|zsh -c`, `eval`, `ssh`, `xargs`, `sudo` (fewer false positives,
  more bypass surface such as `python -c "os.system(...)"`).
- **Recommend A.**

## Q-30 Guard rules stricter than the PKG sample (D-P2-1, C13b)
Whole-token branch match (PKG blocks `git push origin fix/main`), `rm -fr` / `rm -r -f` variants, `more` in the
`.env` rule, and a recursive `rm` of `/`, `~`, `$HOME`, `.`, `..` blocks even without `-f`.
- **Recommend:** accept (every PKG example keeps its behaviour).

## Q-31 Content added beyond the docs (D-P2-4)
1. `.kuanflow/state.json` format `{"work": "<folder>"}` (PKG §6.2 names the file but not its format); W1 and
   debug-incident write it when they create a work folder.
2. fintech-review skips with a note when `risk.fintech` is false and the diff does not touch money.
3. w6-test appends the AC → test map to `plan.md` under `## Test map` (PB W6 asks for the map, not a file).
4. Every `wN` command stops when `wN` is not in `workflows.enabled`.
- **Recommend:** accept all four.
