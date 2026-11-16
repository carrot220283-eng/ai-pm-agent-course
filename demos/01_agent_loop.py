"""01_agent_loop.py —— 一个 Agent 循环，60 行核心，跑三个场景。

跑法：python demos/01_agent_loop.py
不需要 API Key。

三个场景看的是同一件事：**Agent 的可靠性不在模型，在循环的约束**。
  场景 A：正常跑完 —— 看「停机条件」怎么起作用
  场景 B：去掉停机条件 —— 看它怎么烧钱（用 4 次假调用模拟，真模型会烧到你的额度）
  场景 C：工具返回空 —— 看它是重试、还是开始编
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fake_llm import ScriptedLLM, est_tokens  # noqa: E402

# ---------------------------------------------------------------- 工具层
# 每个工具 = 名字 + 给模型看的描述 + 真函数。
# 「给模型看的描述」写歪了，模型就会乱调 —— 这是产品文档问题，不是模型问题。

def search_orders(query: str) -> str:
    if "退款" in query:
        return "订单 A123：2026-11-02 下单，已签收，支持 7 天无理由退款。"
    if "物流" in query:
        return "订单 A123：11-04 已从杭州发出，当前在广州中转。"
    return ""


def calc(expr: str) -> str:
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))  # demo 用，别在生产这么写
    except Exception as exc:  # noqa: BLE001
        return f"计算出错：{exc}"


TOOLS = {
    "search_orders": {
        "fn": search_orders,
        "desc": "按用户问题检索订单信息。入参 query 是用户原话里的关键词，如「退款」「物流」。",
        "params": {"query": "string"},
    },
    "calc": {
        "fn": calc,
        "desc": "计算算术表达式，如「128*0.85」。只接受数字与 + - * / ( )。",
        "params": {"expr": "string"},
    },
}

# 给模型看的工具清单（OpenAI function calling 格式）。
# 注意：产品能改的就是这几行 description —— 模型调错工具，八成是这里没写清。
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": spec["desc"],
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in spec["params"]},
                "required": list(spec["params"]),
            },
        },
    }
    for name, spec in TOOLS.items()
]


# ---------------------------------------------------------------- 循环层
def run_agent(llm, question: str, *, max_steps: int = 5, verbose: bool = True) -> dict:
    """一个最小的 ReAct 循环。四件东西缺一不可：

    1. max_steps      —— 硬上限，防死循环（花的是你的钱）
    2. stop_when      —— 停机条件：模型给出最终答复就停
    3. 重复调用检测    —— 同一个工具同一组参数调两次，就是卡住了
    4. 失败兜底       —— 工具报错/返回空时，不能让模型自由发挥
    """
    messages = [
        {"role": "system", "content": "你是电商客服助手。需要事实时必须调用工具，不许凭记忆回答。"},
        {"role": "user", "content": question},
    ]
    trace = []
    seen_calls = set()

    for step in range(1, max_steps + 1):
        reply = llm.chat(messages, tools=TOOL_SCHEMAS)
        if verbose:
            print(f"  [第 {step} 步] 模型 → {reply['type']}")

        # ---- 停机条件 1：模型给出最终答复
        if reply["type"] == "text":
            trace.append(("final", reply["content"]))
            return {"status": "ok", "answer": reply["content"], "steps": step, "trace": trace}

        name, args = reply.get("name"), reply.get("args") or {}

        # ---- 约束 3：同一个调用重复出现 = 卡住
        sig = (name, tuple(sorted(args.items())))
        if sig in seen_calls:
            trace.append(("loop_detected", name))
            return {"status": "stuck", "answer": "（检测到重复调用，已中止）", "steps": step, "trace": trace}
        seen_calls.add(sig)

        tool = TOOLS.get(name)
        if not tool:
            result = f"没有名为 {name} 的工具。可用工具：{list(TOOLS)}"
        else:
            try:
                result = tool["fn"](**args)
            except Exception as exc:  # noqa: BLE001
                result = f"工具报错：{exc}"

        # ---- 约束 4：空结果必须显式告知，否则模型会开始编
        if not str(result).strip():
            result = "（工具返回空。没有找到相关数据，请如实告知用户，不要猜测。）"

        if verbose:
            print(f"         工具 {name}({args}) → {str(result)[:60]}")
        trace.append((name, result))
        # 真模型（OpenAI 兼容接口）要求把这次工具调用记进历史，
        # 且 tool 消息必须带 tool_call_id，否则第二轮会报 400。
        call_id = f"call_{step}"
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
            }],
        })
        messages.append({"role": "tool", "tool_call_id": call_id, "content": str(result)})

    # ---- 停机条件 2：步数用尽
    return {"status": "max_steps", "answer": "（达到最大步数，未得出结论）", "steps": max_steps, "trace": trace}


def banner(title: str) -> None:
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)


# ---------------------------------------------------------------- 真模型（可选）
# 加了 --real 才会走这段。需要 OPENAI_API_KEY（任何 OpenAI 兼容接口都行）。
if "--real" in sys.argv:
    from fake_llm import OpenAILLM, pick_llm

    real = pick_llm()
    if not isinstance(real, OpenAILLM) or not real.available:
        print("没检测到 OPENAI_API_KEY —— 先设好环境变量，或直接跑脚本模式：")
        print("  python demos/01_agent_loop.py")
        raise SystemExit(1)

    banner(f"真模型模式：同一个循环，换成 {real.name}")
    r = run_agent(real, "我这个订单能退款吗？能的话，退款金额是原价的 85% 是多少？")
    print(f"\n结果：{r['status']}，用了 {r['steps']} 步")
    print(f"回答：{r['answer']}")
    print("\n注意：真模型可能不调工具、可能乱填参数、可能两步就下结论。")
    print("这些都不是循环坏了，是「同一个约束，碰上不确定的模型」。")
    raise SystemExit(0)


# ---------------------------------------------------------------- 场景 A
banner("场景 A：正常跑完（停机条件 = 模型给出最终答复）")
llm_a = ScriptedLLM([
    {"type": "tool", "name": "search_orders", "args": {"query": "退款"}},
    {"type": "text", "content": "订单 A123 已签收，支持 7 天无理由退款，您可以直接申请。"},
])
res = run_agent(llm_a, "我这个订单能退款吗？")
print(f"\n结果：{res['status']}，用了 {res['steps']} 步")
print(f"回答：{res['answer']}")

# ---------------------------------------------------------------- 场景 B
banner("场景 B：去掉停机条件会怎样（模拟 4 步仍在「思考」）")
llm_b = ScriptedLLM([
    {"type": "tool", "name": "search_orders", "args": {"query": "退款"}},
    {"type": "tool", "name": "calc", "args": {"expr": "1+1"}},
    {"type": "tool", "name": "search_orders", "args": {"query": "物流"}},
    {"type": "tool", "name": "calc", "args": {"expr": "2+2"}},
])
res = run_agent(llm_b, "帮我算一下退款金额", max_steps=4)
print(f"\n结果：{res['status']} —— 4 步里没有一步产出结论，这就是「烧钱但没结果」")
print("产品侧的对应动作：把 max_steps 写进 PRD，并约定超限时用户看到什么文案。")

# ---------------------------------------------------------------- 场景 C
banner("场景 C：工具返回空（看它是重试、还是开始编）")
llm_c = ScriptedLLM([
    {"type": "tool", "name": "search_orders", "args": {"query": "发票"}},
    {"type": "text", "content": "系统里没查到您的发票记录，我先帮您转人工，预计 2 小时内回复。"},
])
res = run_agent(llm_c, "我要开发票")
print(f"\n结果：{res['status']}")
print(f"回答：{res['answer']}")
print("\n注意工具那行被替成了「请如实告知，不要猜测」——")
print("它决定了模型是说「没查到」，还是编一个发票号给你。这句兜底文案是产品该盯的。")

# ---------------------------------------------------------------- 收尾
banner("三个数字，回到你的 PRD 里")
ctx = " ".join(str(m.get("content", "")) for m in llm_a.calls[-1])
print("  max_steps         = 4（每多 1 步，成本线性上涨）")
print(f"  单轮上下文 token  ≈ {est_tokens(ctx)}（这还只是 2 步的一次问答）")
print("  停机条件          = 模型给出最终答复 / 步数用尽 / 重复调用 / 工具连续空返回")
