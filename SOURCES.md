# 出处与致谢

## 一、这门课是怎么来的

它起源于一个面试题库仓库：[juliepy/AI-Engineer-from-scrach](https://github.com/juliepy/AI-Engineer-from-scrach)
（中文「人工智能 Agent 方向面试宝典」，作者在 B 站持续更新）。

那个仓库的价值在于**给出了 Agent 工程的问题清单**：一个 AI 工程师到底会被问什么、
哪些环节真的会出事。但它面向的是"能写代码、要去面试工程师岗"的人，
而且内容以可运行示例为主。

这门课做的是另一件事：**把同一批问题，翻译成产品经理能用来做决策的形式。**

## 二、说清楚「没抄」

源仓库**没有开源许可证**（根目录无 LICENSE），按默认版权规则，保留所有权利。
因此本课程：

- **不复制**源仓库的任何原文、代码或目录结构
- 只借用「问题清单」这一层信息——哪些环节值得讲、哪些是真实事故点
- 全部正文、示例、demo 代码均为本课程原创撰写
- demo 里的语料、订单号、政策条款、公司名，全部是虚构的教学素材

如果你在自己的仓库里看到与本课程措辞相似的段落，那来自本课程，不是反过来。

## 三、影响过这门课的公开资料

以下都是公开发表、可自由阅读的一手材料。本课程用自己的话重述了其中的概念，
并在文中标注了它们对应的产品决策——但**没有逐字引用**。

| 主题 | 出处 |
|---|---|
| ReAct（推理与行动交替） | Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models*, 2022. arXiv:2210.03629 |
| Reflexion（失败后自我反思） | Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning*, 2023. arXiv:2303.11366 |
| LATS（树搜索 + 语言模型） | Zhou et al., *Language Agent Tree Search Unifies Reasoning, Acting, and Planning*, 2023. arXiv:2310.04406 |
| RAG（检索增强生成） | Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, 2020. arXiv:2005.11401 |
| Agent 系统的工程模式 | Anthropic, *Building Effective Agents*, 2024 |
| 熔断器模式 | Nygard, *Release It!*, 2007（Circuit Breaker 的经典出处） |
| 上下文窗口与"lost in the middle" | Liu et al., *Lost in the Middle: How Language Models Use Long Contexts*, 2023. arXiv:2307.03172 |

## 四、本课程不做的事

- 不教模型训练、微调、蒸馏（那是另一个岗位的技能）
- 不教具体框架的 API（LangChain / LangGraph / Dify 的用法看官方文档，且会过时）
- 不预测哪家模型会赢（对产品决策没有帮助）
- 不提供"面试原题答案"（第 15 讲给的是**话术结构**，不是标准答案）

## 五、发现错误怎么办

提 issue。这门课的目标不是权威，是**让一个产品经理能在评审会上问出对的问题**。
如果你发现某个数字、某条阈值在你的实际业务里不成立，那正是应该提 issue 的内容——
带上你的场景和实测值，比"这里写错了"有用得多。

## 六、许可

- 文字内容：CC BY-NC-SA 4.0（署名—非商业性使用—相同方式共享）
- 代码（`demos/` 目录）：MIT

商业培训使用请联系作者。个人学习、公司内部传阅、课堂教学，都不需要授权。
