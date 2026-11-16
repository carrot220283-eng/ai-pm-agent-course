"""fake_llm.py —— 让 demo 不花钱、不联网、可复现。

两种用法：

1) ScriptedLLM：按脚本吐回复。用来演示「机制」，不演示「智能」。
   llm = ScriptedLLM([
       {"type": "tool", "name": "search", "args": {"q": "退款"}},
       {"type": "text", "content": "查到了：7 天内可退。"},
   ])

2) OpenAILLM：有 OPENAI_API_KEY 时走真模型，没 key 会自动退回脚本模式。
   注意：真模型的输出不可复现，跑 demo 时建议用脚本模式。

为什么不用 openai 官方 SDK：本仓库坚持零第三方依赖，任何人 clone 下来就能跑。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

# Windows 控制台默认 GBK，直接 print 中文会乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


class ScriptedLLM:
    """按顺序吐出预设回复；脚本用完后一直返回最后一条，避免 demo 崩掉。"""

    def __init__(self, script: list[dict], name: str = "scripted"):
        self.script = list(script)
        self.name = name
        self.calls: list[list[dict]] = []  # 记录每次收到的 messages，方便复盘
        self._i = 0

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        self.calls.append([dict(m) for m in messages])
        if self._i < len(self.script):
            step = self.script[self._i]
            self._i += 1
        else:
            step = {"type": "text", "content": "（脚本已用完，这是兜底回答）"}
        return dict(step)


class OpenAILLM:
    """最小可用的真模型客户端：只用标准库。"""

    def __init__(self, model: str = "gpt-4o-mini", base_url: str | None = None):
        self.model = model
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL")
                         or "https://api.openai.com/v1").rstrip("/")
        self.key = os.environ.get("OPENAI_API_KEY")
        self.name = f"openai:{model}"

    @property
    def available(self) -> bool:
        return bool(self.key)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if not self.key:
            raise RuntimeError("没有 OPENAI_API_KEY，请用 ScriptedLLM")
        body: dict = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        if msg.get("tool_calls"):
            call = msg["tool_calls"][0]
            return {"type": "tool",
                    "name": call["function"]["name"],
                    "args": json.loads(call["function"]["arguments"] or "{}")}
        return {"type": "text", "content": msg.get("content") or ""}


def pick_llm(script: list[dict] | None = None) -> "ScriptedLLM | OpenAILLM":
    """有 key 用真模型，没 key 用脚本 —— 让 demo 在任何人机器上都能跑。"""
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAILLM()
    return ScriptedLLM(script or [])


def est_tokens(text: str) -> int:
    """粗估 token：中文约 1 字 1 token，英文约 4 字符 1 token。

    真实分词器会差 ±30%，但对「判断上下文会不会爆」足够了。
    工程报成本时用的是真实计数，你拍预算时用这个估算就行。
    """
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    rest = len(text) - cjk
    return int(cjk + rest / 4)


if __name__ == "__main__":
    demo = ScriptedLLM([{"type": "text", "content": "你好，我是脚本模型。"}])
    print(demo.chat([{"role": "user", "content": "hi"}]))
    print("估算 token：", est_tokens("这是一段中文，mixed with English words."))
