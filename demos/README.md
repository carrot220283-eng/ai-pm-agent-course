# demos —— 五个能跑的小程序

这五个 demo 加起来不到 600 行，零第三方依赖，`python demos/0X_*.py` 挑一个直接跑（Windows 的 PowerShell 里也一样）。
它们不是「教学示例」，是**五个可以拿去和工程对话的证据**。

| 文件 | 对应课 | 它证明了什么 |
|---|---|---|
| `01_agent_loop.py` | 第 01 讲 | Agent 就是一个循环；四个约束（max_steps / 停机 / 重复检测 / 空结果兜底）里任何一个缺席都会出事 |
| `02_rag_pipeline.py` | 第 04 讲 | RAG 的效果上限 = 召回上限；幻觉长什么样、为什么长得像对的 |
| `03_context_budget.py` | 第 06 讲 | 上下文是固定预算的背包；「忘记」往往是设计缺陷，不是模型缺陷 |
| `04_breaker_retry.py` | 第 09 讲 | 重试会把小故障放大成雪崩；熔断牺牲一点成功率换系统存活 |
| `05_eval_set.py` | 第 05、11 讲 | 把「我觉得好点了」变成三个可打分的数字，并给出上线门禁判定 |

## 跑法

```bash
python demos/01_agent_loop.py
python demos/02_rag_pipeline.py
python demos/03_context_budget.py
python demos/04_breaker_retry.py
python demos/05_eval_set.py
```

要求：Python 3.9+。Windows 控制台如果中文乱码，每个文件开头已经做了 UTF-8 重定向，直接跑就行。

## 关于真模型

`01_agent_loop.py` 默认用 `fake_llm.ScriptedLLM`——一个按剧本回话的假模型，
这样你不需要 API Key 也能看清循环的所有分支。

想接真模型，设两个环境变量即可（走 OpenAI 兼容接口，任何厂商都行）：

```bash
set OPENAI_API_KEY=sk-xxx
set OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或任何兼容地址
python demos/01_agent_loop.py --real
```

**建议先跑假模型。** 假模型的行为是确定的，你能反复对照输出理解机制；
接上真模型之后，你会分不清「这是机制问题」还是「这是模型这次抽风」。

## 改它们，别只跑它们

每个 demo 里都留了「改一下会怎样」的练习（如 `max_steps` 改成 2、k 从 1 改到 5）。
**看着输出变化的那一下，才是学习发生的时候。** 只跑一遍的输出，看十次也记不住。

## 一个约定

这些 demo 里所有的「模型回答」都是写死的字符串，不是真的调模型。
这不是偷懒——是为了让你看清楚：**产品要定义的是规则和兜底，不是某一次回答。**
真模型只是把这些写死的地方换成了它的输出，规则一条都不能少。
