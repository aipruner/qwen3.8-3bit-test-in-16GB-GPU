DFlash 2 + ngram-mod (`./ops/qwen38.sh dflash-ngram`). 8K q4_0 n-max 3.

16K q4_0 n-max 4 looked like a fit on a 32-token probe, then 5.1 tokens/sec
on a 600-token write. Do not use that window.

See `docs/06-ngram.md`. Pair with `../mtp-ngram/`.
