Reddit 上有人在 16GB 卡把 ngram-mod 叠在 MTP 或 DFlash 2 上，把 context 开到十万。我没换量化，还是上一篇的 Qwen3.8-27B 3-bit（UD-Q3_K_XL）、同一张 5070 Ti。只比三件事：ngram 是什么、谁能开更大、谁更适合当 agent。

先说 ngram-mod：它不是第二颗模型。llama.cpp 在内存里放一张约 400 万格的哈希表，大约 16 MB RAM，几乎不占显存。最近 N 个 token 以前出现过，就把「上次后面接什么」提出来当草稿，主模型还是逐个验收。JSON 工具调用这种重复形状它猜得准；没见过的中文散文几乎帮不上。可以和 MTP 或 DFlash 2 用逗号叠在 `--spec-type` 里，但这两种神经草稿仍只能选一个。ngram 也不会让 KV cache 变便宜。

能开多大，实测还是 MTP 赢。ngram + MTP：8K / 16K / 24K q8_0 都过，32K 溢出。ngram + DFlash 2：q8_0 从 8K 到 16K 全溢出。16K q4_0 的 32 token 探针写了 60.8，拿去写 600 个 token 掉到每秒 5.1 个——探针会骗人。真正站得住的工作点是 8K、q4_0、n-max 3，600 token 生成速度 92.0。对方能开 105K，是目标量化更瘦，不是把 ngram 叠上去就会变出来。

加盐的 600 token 平均生成速度：ngram + MTP 每秒 94.6 个 token，ngram + DFlash 2 是 78.0。繁中散文 73.7 vs 59.7。另外出了 25 行几乎同款的 JSON 工具调用：124.5 vs 109.1。固定格式两边都比散文快，拿聊天测速度还是会低估 agent。

同一套读文件、写文件、跑测试的 ReAct harness 去修 QuixBugs 29 题：ngram + MTP（24K）28/29，492 秒，171 次工具调用，循环里平均 105.2 tokens/秒，失败仍是 lis，格式错误 0，改测试 0。ngram + DFlash 2（8K）24/29，783 秒，多挂四题，平均 78.0。上一篇没加 ngram 的 24K MTP 是 27/29、589 秒；28 对 27 是 temperature 0.7 的单次，不要写成 ngram 比较会修。能讲的是 8K 少修四题、多花 291 秒。

数学给 Python 工具：MTP 那组 7/8（Pell 方程没讲完），DFlash 那组 8/8 但更慢。单次不要倒过来当结论。日常我开 24K 的 `safe` 或 `safe-ngram`。

完整 log：https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
