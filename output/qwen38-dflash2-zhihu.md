# 知乎 — DFlash2 对照实测

用一张 16GB 的 5070 Ti 跑 Qwen3.8-27B 3-bit 的后续。上一篇是模型自带的 MTP（Multi-Token Prediction），24K context，QuixBugs 29 题修 27 题，数学给 Python 工具 8/8。两天后 Reddit 上有人在 4080 16GB 上用 DFlash 2 草稿把 context 开到 105K。草稿文件是现成的，大约 1.1 GB。我没换量化，还是那个 `UD-Q3_K_XL`。问题只有一句：同一套 DFlash 2，换到我这个更肥的 3-bit 文件上，还剩什么？

先说结论：在这个文件上，DFlash 2 不是加速器。它用 context 换来另一种草稿。105K 那组旗标会溢出；真正站得住的工作点是 8K。8K 对 8K，平均生成速度和原生 MTP 差不多，中文更慢。

现成的 `llama.cpp` Docker 镜像载不进 DFlash 2，报 `expected 81, got 58` tensors，要自己编 [PR #27342](https://github.com/ggml-org/llama.cpp/pull/27342)。编完之后，对方的 n-max 5、q5_1、105K 在 `UD-Q3_K_XL` 上生成速度掉到每秒 2 到 4 个 token。WSL2 不报 OOM，`/health` 照样回 ok。上一篇测 4-bit 就是这个坑。对方能开 105K，是因为目标量化 `RVN-IQ3_XXS` 更瘦，不是 DFlash 2 魔法。

我的工作点：8192 context、KV q8_0、n-max 4、草稿也放 GPU，大约 15,069 MiB。32 个 token 的探针 68.2 tokens/秒。

同一份编译、同一个 8K、prompt 前面加随机盐（不然 llama.cpp 的 prefix cache 会灌水），各写约 600 个 token：

- Python LRU：DFlash 2 每秒 114.4 个 token，MTP 110.0
- HTML：110.4 vs 121.6
- 英文散文：81.3 vs 76.7
- 繁中散文：62.7 vs 80.7
- 平均：92.2 vs 97.2

中文散文的草稿接受率 340/1031，只有 33%。MTP 猜固定格式本来就准，上一篇写过工具调用每秒 113、写中文散文只剩 80。DFlash 2 在中文上更差。

同一套品质测试，采样仍是 `temperature=0.7, top_p=0.8`：

QuixBugs 28/29，738 秒，165 次工具调用，格式错误 0，改测试作弊 0。上一篇 27/29、589 秒。失败的还是 `lis`。`subsequences` 这次过了，单次不能解释成「比较会修」。循环里平均生成速度 60.5，上一篇大约 90 到 110。

俄罗斯方块平均 38 秒（上一篇 35），功能检查 14/14，`node --check` 2/3，有一次 `else` 语法错。

数学八道，标准答案仍是本机暴力法先算过。只让它想：3/8，451 秒，五题失败全部是想完没讲完。给 Python 工具：7/8，336 秒；上一篇 8/8、123 秒。挂掉的是 Pell 方程，169 秒、两次工具、没有 `ANSWER:`。8K 被思考加工具记录填满，截断了。「3 的 1000 次方各位数字加起来」给工具 7 秒就对。给工具还是比给思考时间划算；这回多一句：工具循环自己也要吃 context，砍窗口会切到会东想西想的题。沉默还是比讲错安全——它没给我一个错的 17 亿，是没讲完。

我没测对方的 `IQ3_XXS`，没把 ngram-mod 当默认（prefix cache 会让没加盐的数字很好看），没重跑上一篇那只骑脚踏车的鹈鹕。日常仍开 24K 原生 MTP。DFlash 2 值得试的条件是你换更瘦的目标量化，显存同时塞得下草稿和长 context。那是对方那篇在做的事，不是把旗标贴到 `UD-Q3_K_XL` 上。

完整 log 和启动器在 GitHub：https://github.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU
上一篇 Medium：https://medium.com/@aipruner1991/qwen3-8-27b%E5%AF%A6%E6%B8%AC-5070ti-16gb-gpu-e72cddbb78e1
