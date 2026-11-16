"""03_context_budget.py —— 上下文是一个固定预算的背包，装满了就要扔东西。

跑法：python demos/03_context_budget.py

看三件事：
  场景 A：一次正常对话，背包还剩多少
  场景 B：用户上传一份 30 页文档 + 聊到 60 轮，背包爆了 —— 被扔的是谁
  场景 C：被扔掉的恰好是"用户早先说过的硬约束"，于是模型开始违规
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fake_llm import est_tokens  # noqa: E402

WINDOW = 32_000          # 假设用的是 32k 窗口的模型
MAX_STEPS_NOTE = "注意：token 是估算值，真实分词会差 ±30%，但够用来判断「会不会爆」"


def bar(used: int, total: int, width: int = 34) -> str:
    filled = min(width, round(used / total * width))
    return "█" * filled + "·" * (width - filled)


def show(title: str, items: list[tuple[str, int]], window: int = WINDOW) -> None:
    total = sum(t for _, t in items)
    print(f"\n{title}")
    print("-" * 66)
    print(f"{'组件':<26}{'token':>8}{'占比':>9}   ")
    for name, tok in items:
        print(f"{name:<26}{tok:>8}{tok / window * 100:>8.1f}%   {bar(tok, window, 20)}")
    print("-" * 66)
    print(f"{'合计':<26}{total:>8}{total / window * 100:>8.1f}%   {bar(total, window)}")
    left = window - total
    print(f"{'剩余可给推理':<24}{left:>8}{left / window * 100:>8.1f}%")
    if total > window:
        print(f"⚠ 超了 {total - window} token —— 这时候不是「慢一点」，是直接报错或被截断")


SYSTEM = (
    "你是电商售后助手。只根据检索到的订单与政策作答，不确定就说不确定。"
    "用户预算上限、退款时限等硬约束必须遵守。"
)
TOOLS_DESC = [(f"工具{i}", 150) for i in range(1, 19)]   # 18 个工具，每个 150 token
HISTORY_TURN = ("一轮对话（用户+助手）", 300)
DOC_PAGE = ("上传文档一页（约 500 字）", 500)

print("=" * 66)
print("场景 A：一次普通的 5 轮对话")
print("=" * 66)

items_a = [
    ("system prompt（规则）", est_tokens(SYSTEM)),
    *TOOLS_DESC,
    ("检索结果（5 段）", 5 * 480),
    ("对话历史（5 轮）", 5 * HISTORY_TURN[1]),
    ("当前问题", 40),
]
show("背包明细", items_a)
print(f"\n{MAX_STEPS_NOTE}")
print("结论：一次短对话只用掉一成多。你会觉得「窗口很够」—— 这就是误判的起点。")

print("\n" + "=" * 66)
print("场景 B：用户上传了一份 30 页合同，又聊了 60 轮")
print("=" * 66)

items_b = [
    ("system prompt（规则）", est_tokens(SYSTEM)),
    *TOOLS_DESC,
    ("上传文档（30 页）", 30 * DOC_PAGE[1]),
    ("检索结果（5 段）", 5 * 480),
    ("对话历史（60 轮）", 60 * HISTORY_TURN[1]),
    ("当前问题", 40),
]
show("背包明细（未裁剪）", items_b)

total_b = sum(t for _, t in items_b)
need_cut = total_b - WINDOW
print(f"\n需要扔掉 {need_cut} token 才能装下。谁来扔？通常的裁剪顺序是：")
print("  1) 先扔最老的历史  2) 再扔工具描述  3) 再减检索段数  4) 最后才动 system prompt")
print("\n于是，被扔掉的往往是——用户在第 2 轮说过的那句话。")

print("\n" + "=" * 66)
print("场景 C：被扔掉的是硬约束，模型开始违规")
print("=" * 66)

dropped = "【第 2 轮 用户】我这个月预算最多 500 元，超了就别给我方案了。"
print(f"被裁掉的内容：{dropped}")
print(f"（它现在不在上下文里了，模型看不到，也就不会遵守）")
print()
print("模型基于剩下的信息给出的建议：")
print("  「建议您升级到尊享版，年费 899 元，可享全年免运费。」")
print()
print("用户视角：它明明答应过我。")
print("工程视角：那是 4 万 token 之前的事了，早被裁了。")
print("产品视角：这是设计缺陷 —— 我们把长期有效的约束，放在了会被丢弃的位置。")

print("\n修法（三选一，成本递增）：")
print("  a. 硬约束写进 system prompt（几乎免费，但需要产品事先想清楚「哪些是不能忘的」）")
print("  b. 做摘要压缩：每 N 轮把历史压成一句「已知约束」（中等成本，有损）")
print("  c. 做长期记忆：把约束抽成结构化字段存起来，每轮注入（成本最高，最可靠）")
print("\n产品决策：这三条不是技术选型，是「你的产品允不允许它忘事」的承诺。")
print("           → 合同/医疗/金额类场景选 c；闲聊场景 a 就够。")

print("\n" + "=" * 66)
print("一句话带走")
print("=" * 66)
print("上下文不是「越大越好」，是「你决定什么必须一直在里面」。")
print("这句话写进 PRD 的『记忆与上下文』一节，比写「支持长上下文」有用 100 倍。")
