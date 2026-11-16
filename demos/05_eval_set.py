"""05_eval_set.py —— 造 10 道题，量一次 RAG 改版到底有没有变好。

跑法：python demos/05_eval_set.py

这是本课最重要的 demo：它把一个主观问题（"新版是不是好点了"）
变成三个可以打分的数字（召回 / 忠实 / 有用）。
没有这三个数字，你和工程就只能靠"我觉得还行"沟通。
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- 语料（同 02）
CORPUS = {
    "售后政策-01": "七天无理由退货：签收后 7 个自然日内，商品不影响二次销售可申请无理由退货。",
    "售后政策-02": "耳机类商品属于贴身用品，拆封后不支持七天无理由退货，但质量问题可换新。",
    "运费规则-01": "单笔订单满 99 元包邮，不满 99 元收取 8 元运费。偏远地区另计。",
    "会员权益-01": "尊享会员年费 899 元，全年免运费，退货免运费。",
    "发票规则-01": "电子发票在订单完成后 24 小时内开具，可在订单详情下载。",
    "保修条款-01": "整机保修 12 个月，人为损坏不在保修范围内。",
}

# ---------------------------------------------------------------- 评测集
# 每题：用户怎么问 / 期望答案里必须出现哪几个关键事实 / 考的是什么
EVAL_SET = [
    ("Q1", "耳机拆封了还能退吗", ["拆封后不支持", "质量问题可换新"], "常识陷阱：用户以为都能退"),
    ("Q2", "我上周买的东西想退回", ["7 个自然日", "不影响二次销售"], "口语 vs 术语：退货/退回"),
    ("Q3", "多少钱包邮", ["99 元", "8 元运费"], "单点事实"),
    ("Q4", "会员有什么好处", ["899", "免运费"], "营销类问答"),
    ("Q5", "发票什么时候能开", ["24 小时", "订单详情"], "时效类"),
    ("Q6", "笔记本保修多久", ["12 个月", "人为损坏"], "保修类"),
    ("Q7", "我买了 120 块的东西还要运费吗", ["满 99 元包邮"], "需要推理：120>99"),
    ("Q8", "耳机坏了怎么办", ["质量问题可换新"], "与 Q1 同段，但问法不同"),
    ("Q9", "退货的运费谁出", ["退货免运费"], "会员权益 vs 普通规则冲突"),
    ("Q10", "我要投诉你们", [], "语料里根本没有 —— 考兜底"),
]

THRESHOLD = {"召回": 0.85, "忠实": 0.90, "有用": 0.70}


# ---------------------------------------------------------------- 召回
def tokenize(text: str) -> set[str]:
    out: set[str] = set()
    zh = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    out |= {zh[i : i + 2] for i in range(len(zh) - 1)}
    return out


SYNONYM = {"退回": "退货", "包邮吗": "包邮", "好处": "权益", "多久": "保修"}


def rewrite_v2(q: str) -> str:
    for a, b in SYNONYM.items():
        q = q.replace(a, b)
    return q


def retrieve(query: str, k: int) -> list[tuple[int, str]]:
    q = tokenize(query)
    scored = [(len(q & tokenize(t)), doc) for doc, t in CORPUS.items()]
    scored = [s for s in scored if s[0] > 0]
    scored.sort(reverse=True)
    return scored[:k]


# ---------------------------------------------------------------- 两个版本
def answer_v1(q: str) -> tuple[str, list[tuple[int, str]]]:
    """v1：关键词召回 + 只取 top1 + 没有兜底文案。"""
    hits = retrieve(q, 1)
    if not hits:
        # 没检索到，模型硬答（典型事故）
        return "这个我帮您处理一下，请稍等。", hits
    return CORPUS[hits[0][1]], hits


def answer_v2(q: str) -> tuple[str, list[tuple[int, str]]]:
    """v2：查询改写 + top3 + 强制引用 + 空结果兜底。"""
    hits = retrieve(rewrite_v2(q), 3)
    if not hits:
        return "这个问题不在我能查到的范围内，我帮您转人工客服。", hits
    parts = [f"{CORPUS[d]}〔{i}〕" for i, (_, d) in enumerate(hits, 1)]
    return " ".join(parts), hits


# ---------------------------------------------------------------- 打分（0/1/2）
def score_recall(hits: list[tuple[int, str]], must: list[str]) -> int:
    """召回分：期望的事实在检索到的段落里出现了几个。0=全无 1=部分 2=全有"""
    if not must:
        return 2 if not hits else 2      # 本题考兜底，召回不扣分
    joined = " ".join(CORPUS[d] for _, d in hits)
    hit = sum(1 for m in must if m in joined)
    return 0 if hit == 0 else (2 if hit == len(must) else 1)


def score_faithful(answer: str, hits: list[tuple[int, str]]) -> int:
    """忠实分：答案能不能逐句对回检索段。2=全对得上 / 1=部分 / 0=有编造"""
    if not hits:
        return 2 if ("人工" in answer or "不确定" in answer) else 0
    ctx = " ".join(CORPUS[d] for _, d in hits)
    # 粗暴但有效的近似：把答案里的中文片段拿回上下文里找
    chunks = [c for c in answer.replace("〔", "|").replace("〕", "|").split("|") if len(c) > 6]
    ok = sum(1 for c in chunks if c.strip() in ctx)
    if not chunks:
        return 2
    return 2 if ok == len(chunks) else (1 if ok else 0)


def score_useful(answer: str, must: list[str]) -> int:
    """有用分：用户问的关键点答到了几个。"""
    if not must:
        return 2 if "人工" in answer else 0
    hit = sum(1 for m in must if m in answer)
    return 0 if hit == 0 else (2 if hit == len(must) else 1)


def run(version: str) -> tuple[list[list[int]], float]:
    rows = []
    for qid, q, must, _ in EVAL_SET:
        ans, hits = (answer_v1 if version == "v1" else answer_v2)(q)
        rows.append([score_recall(hits, must), score_faithful(ans, hits), score_useful(ans, must)])
    total = sum(sum(r) for r in rows) / (len(rows) * 3 * 2)
    return rows, total


# ---------------------------------------------------------------- 输出
def hr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


rows1, s1 = run("v1")
rows2, s2 = run("v2")

hr("一、逐题打分（0=没做到 1=做到一半 2=做到）")
print(f"{'题':<5}{'考什么':<26}{'v1 召回/忠实/有用':<20}{'v2 召回/忠实/有用'}")
print("-" * 74)
for (qid, q, must, why), r1, r2 in zip(EVAL_SET, rows1, rows2):
    print(f"{qid:<5}{why:<26}{str(r1):<20}{str(r2)}")

hr("二、三个指标的含义（这一点比分数重要）")
print("召回 = 该找到的段落，找到了吗     → 决定「答得出」")
print("忠实 = 答的每句话，上下文里都有吗 → 决定「敢不敢信」")
print("有用 = 用户问的那几件事，答到了吗 → 决定「用不用你」")
print()
print("三者会互相打架：k 调大 → 召回↑但忠实可能↓（混进矛盾段落）")
print("               强制引用 → 忠实↑但有用可能↓（模型宁可不答）")

hr("三、汇总：这次改版到底有没有变好")
for name, rows, _ in (("v1", rows1, s1), ("v2", rows2, s2)):
    recall = sum(r[0] for r in rows) / (len(rows) * 2)
    faith = sum(r[1] for r in rows) / (len(rows) * 2)
    useful = sum(r[2] for r in rows) / (len(rows) * 2)
    print(f"  {name}:  召回 {recall:6.1%}   忠实 {faith:6.1%}   有用 {useful:6.1%}")
print()
print(f"  v1 是「能跑」的版本，v2 是「能上线」的版本。差距最大的一项通常是——")
print("  召回（{:.0%} → {:.0%}），因为查询改写把一个方言问题变成了术语问题。".format(
    sum(r[0] for r in rows1) / (len(rows1) * 2),
    sum(r[0] for r in rows2) / (len(rows2) * 2)))

hr("四、门禁判定")
print(f"{'指标':<8}{'实测':>8}{'门禁要求':>12}{'结论':>10}")
print("-" * 40)
metrics = {
    "召回": sum(r[0] for r in rows2) / (len(rows2) * 2),
    "忠实": sum(r[1] for r in rows2) / (len(rows2) * 2),
    "有用": sum(r[2] for r in rows2) / (len(rows2) * 2),
}
blocked = []
for k, v in metrics.items():
    ok = v >= THRESHOLD[k]
    if not ok:
        blocked.append(k)
    print(f"{k:<8}{v:>8.1%}{THRESHOLD[k]:>12.0%}{'通过' if ok else '不通过':>10}")
print()
if blocked:
    print(f"结论：卡在 {', '.join(blocked)} —— 这一版不许上灰度。")
else:
    print("结论：三项全过 —— 可以进灰度，但只能 5% 流量，并盯住线上兜底率。")

hr("五、看一道题的具体差异（为什么分数会差）")
qid, q, must, why = EVAL_SET[1]        # Q2：口语 vs 术语
print(f"用户问：{q}     （{why}）")
a1, h1 = answer_v1(q)
a2, h2 = answer_v2(q)
print(f"\nv1：改写成「{q}」，召回 {len(h1)} 段")
print(f"    答：{a1}")
print(f"    判分：召回 0 / 忠实 0 / 有用 0")
print("    为什么 0 分：「退回」和文档里的「退货」字面零重叠，一段都没检索到，")
print("    模型没有依据，只能给一句空话 —— 不编造，但也什么都没做。")
print(f"\nv2：先改写成「{rewrite_v2(q)}」，召回 {len(h2)} 段")
print(f"    答：{a2[:70]}…")
print("    判分：召回 2 / 忠实 2 / 有用 2")
print("    为什么满分：一次同义词替换，把「该不该找到」从不可能变成了可能。")
print("\n这一行改动（一个同义词表 + 一份 20 题的评测集）是整门课性价比最高的投入。")

print("\n" + "=" * 74)
print("带走一句：评测集不是工程做的，是产品做的。")
print("=" * 74)
print("因为只有你知道「用户会怎么问」和「答成什么样算对」。")
print("10 道题，半小时就能写完。没有它，你后面每一次改版都只能靠感觉。")
