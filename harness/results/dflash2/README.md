Raw logs for the 2026-08-21 DFlash 2 run (`./ops/qwen38.sh dflash`).

See `docs/05-dflash2.md` for the narrative and `README.md` for the comparison table.

| File | What |
|---|---|
| `fit.log`, `fit-raw.jsonl` | First CPU-draft / spill ladder |
| `fit-gpu.log`, `fit-gpu2.log` | GPU-draft VRAM probes. Winner: 8K q8_0 n-max 4 |
| `specspeed.log` | 600-token cache-busted speed vs output type |
| `mathtest-tool.log` / `mathtest-reason.log` | 8 math problems |
| `tetris.log` | Three one-shot Tetris generations |
| `quixfix.log` / `quixfix.json` | 29 QuixBugs programs |

`quix_runs/` is gitignored (sandboxes). Fair MTP-at-8K specspeed is in `../mtp/specspeed-8k.log`.
