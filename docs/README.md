# docs/ — notes for the next human or agent

Numbered files are session notes, not published articles. Published write-ups
live in `output/` (mostly gitignored). Raw measurements live in
`harness/results/`.

| File | When | What |
|---|---|---|
| [00-deployment-report-zh.md](00-deployment-report-zh.md) | 2026-08-19 | First deployment write-up |
| [01-what-was-done.md](01-what-was-done.md) | 2026-08-19 | Session changelog (models, scripts, what was stopped) |
| [02-operations.md](02-operations.md) | 2026-08-19 | How to start/stop. **Profiles table is stale** — `ops/qwen38.sh` is the source of truth. `agent` at 32K spills; daily driver is `safe` (24K MTP). DFlash 2 is `dflash` |
| [03-research-report.md](03-research-report.md) | 2026-08-19 | Background research dump |
| [04-benchmarks.md](04-benchmarks.md) | 2026-08-19 | First MTP benchmark notes |
| [05-dflash2.md](05-dflash2.md) | 2026-08-21 | **Read this before changing DFlash flags.** Fit ladder, specspeed, quality suite |
| [sources/reddit-buffmcbighuge-dflash2.md](sources/reddit-buffmcbighuge-dflash2.md) | 2026-08-20 | Clipping of the r/LocalLLaMA post. Not our measurements |

Launcher source of truth: `ops/qwen38.sh` in this repo.
`~/.local/bin/qwen38` should symlink here, not to `/home/kino/models/qwen3.8-27b/_ops/`.
