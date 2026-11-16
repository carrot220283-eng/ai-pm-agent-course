"""02_rag_pipeline.py —— 一条最小的 RAG 链路，以及它最短的三种死法。

跑法：python demos/02_rag_pipeline.py

这条链路只有四步（真实系统是五步，多一个「重排」）：
    切分 → 召回（关键词打分）→ 拼上下文 → 生成（带引用）
故意用关键词召回而不是向量，因为它可解释：你能亲眼看见「为什么这段话没被找出来」。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fake_llm import est_tokens  # noqa: E402

# ---------------------------------------------------------------- 语料
# 真实系统里这是几百份文档切出来的几千段。这里六段，覆盖六个不同的知识点。
CORPUS = [
    ("售后政策-01", "七天无理由退货：签收后 7 个自然日内，商品不影响二次销售可申请无理由退货。"),
    ("售后政策-02", "耳机类商品属于贴身用品，拆封后不支持七天无理由退货，但质量问题可换新。"),
    ("运费规则-01", "单笔订单满 99 元包邮，不满 99 元收取 8 元运费。偏远地区另计。"),
    ("会员权益-01", "尊享会员年费 899 元，全年免运费，退货免运费。"),
    ("发票规则-01", "电子发票在订单完成后 24 小时内开具，可在订单详情下载。"),
    ("保修条款-01", "整机保修 12 个月，人为损坏不在保修范围内。"),
]

# ---------------------------------------------------------------- 召回
def tokenize(text: str) -> set[str]:
    """极简：中文按二元字组切，英文按空格切。够用来演示「召回靠字面重叠」。"""
    out: set[str] = set()
    zh = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    out |= {zh[i : i + 2] for i in range(len(zh) - 1)}
    out |= {w.lower() for w in text.replace("，", " ").replace("。", " ").split()
            if w.isascii() and w.isalpha()}
    return out


def retrieve(query: str, k: int = 3) -> list[tuple[float, str, str]]:
    q = tokenize(query)
    scored = []
    for doc_id, text in CORPUS:
        hit = q & tokenize(text)
        if hit:
            scored.append((len(hit), doc_id, text))
    scored.sort(reverse=True)
    return scored[:k]


# ---------------------------------------------------------------- 生成（模拟）
def generate_with_context(question: str, hits: list[tuple[float, str, str]]) -> str:
    if not hits:
        return "（检索为空）我不确定，建议咨询人工客服。"
    lines = ["根据以下资料作答，每句结论后标注来源编号。"]
    for i, (_, doc_id, text) in enumerate(hits, 1):
        lines.append(f"[{i}] {doc_id}：{text}")
    prompt = "\n".join(lines)
    print(f"    （送进模型的上下文约 {est_tokens(prompt)} token）")
    # 模拟：模型把每条命中各取一句，标上引用编号（真实模型会做综合，这里保持可追溯）
    parts = [f"{text}〔{i}〕" for i, (_, _, text) in enumerate(hits, 1)]
    return " ".join(parts)


def generate_without_context(question: str) -> str:
    """没有检索、只靠模型记忆的版本。这里写死了一句「模型会说的话」。"""
    return "耳机拆封后我们支持 30 天无理由退货，您放心购买。（来源：无）"


# ---------------------------------------------------------------- 三个场景
def hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


hr("场景 A：只取 1 条 vs 取 3 条 —— 差的是「答一半」")
q1 = "耳机拆封了还能退吗，退货运费谁出"
hits1 = retrieve(q1, k=3)
print(f"问题：{q1}")
print("召回结果（按字面重叠打分）：")
for score, doc_id, text in hits1:
    print(f"  {score:>2} 分  {doc_id}  {text[:34]}…")
print("\n只用 top1 生成（很多 demo 到这里就结束了）：")
print("  " + generate_with_context(q1, hits1[:1]))
print("\n取 top3 生成（真实系统会这样）：")
print("  " + generate_with_context(q1, hits1))
print("\n差别在哪：top1 回答了「能不能退」，完全没回答「运费谁出」。")
print("用户问了两件事，只答了一件 —— 这类问题不会报错，只会让用户觉得「它没听懂」。")

hr("场景 B：查不到 —— 关键词召回的死角")
q2 = "我上个礼拜买的东西想退回"
hits2 = retrieve(q2, k=3)
print(f"问题：{q2}")
if not hits2:
    print("召回结果：空！")
    print("\n为什么？因为用户说的是「退回」，文档里写的是「退货」，字面零重叠。")
    print("这类问题在真实系统里占比 20%–40%，是「用户说人话 vs 文档写术语」的鸿沟。")
    print("\n三条修法（成本递增）：")
    print("  1. 查询改写：先用模型把「退回」改写成「退货」，再检索（最常用）")
    print("  2. 用向量召回：语义相近就命中，不再依赖字面（换掉召回层）")
    print("  3. 建同义词表：人工维护「退回/退货/退换」映射（最便宜，最难覆盖全）")

hr("场景 C：不检索直接答 —— 幻觉是怎么长出来的")
print(f"问题：{q1}")
print("没有检索、直接问模型：")
print("  " + generate_without_context(q1))
print("\n对照语料里的真实政策（售后政策-02）：")
print("  耳机拆封后不支持七天无理由退货，但质量问题可换新。")
print("\n注意它甚至编了一个「来源：无」——如果这句换成「来源：官方售后政策」，")
print("用户就再也不会怀疑了。**幻觉最危险的地方不是错，是它长得很像对的。**")

hr("三个数字，决定这条链路的成败")
print(f"语料规模：{len(CORPUS)} 段（真实系统 10^3–10^5 段）")
print(f"单次上下文：约 {est_tokens(''.join(t for _, t in CORPUS)) // 10} token（3 段）")
print("召回命中率：场景 A 命中、场景 B 未命中 —— 这一项低于 85%，生成再好也救不回来")
print("忠实度：生成的内容能否逐句对回检索段 —— 这一项低于 90%，就是在编")
print("有用性：答的是不是用户问的 —— 前两项满分、这一项不及格的产品到处都是")

hr("症状 → 病灶 → 手术 → 代价")
rows = [
    ("答得对但答一半", "只取 top1，上下文给少了", "k 从 1 调到 3–5，让模型综合", "token 成本×3"),
    ("该查到的没查到", "召回靠字面，用户说人话", "查询改写 / 换向量召回", "多一次模型调用"),
    ("答得很像但全是编的", "上下文里没有，模型也不想说不知道", "强制引用 + 空结果兜底文案", "拒答率上升 3%–8%"),
    ("同一个问题两次答不一样", "k 太大，召回了互相矛盾的段落", "加重排，把最相关的顶到第 1", "多一次重排延迟"),
]
w = (22, 26, 26, 18)
print(f"{'症状':<{w[0]}}{'病灶':<{w[1]}}{'手术':<{w[2]}}{'代价'}")
print("-" * 92)
for r in rows:
    print(f"{r[0]:<{w[0]}}{r[1]:<{w[1]}}{r[2]:<{w[2]}}{r[3]}")

print("\n最后一句：RAG 的效果上限 = 召回上限。")
print("召回没找到的东西，提示词写得再漂亮也变不出来。")
