"""04_breaker_retry.py —— 为什么「多重试几次」会把小故障变成大雪崩。

跑法：python demos/04_breaker_retry.py

同一个故障场景（下游 9 秒不可用），用三种策略跑一遍：
    A. 不重试，失败就报错
    B. 失败重试 3 次（最常见的「提高成功率」做法）
    C. 重试 + 熔断器 + 降级兜底
看的不是谁成功率最高，是谁**没有把下游打死**。
"""

from __future__ import annotations

import sys

# Windows 控制台默认 GBK，中文会乱码；强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- 故障现场
TOTAL_REQUESTS = 40          # 40 个用户请求
ARRIVE_EVERY = 0.5           # 每 0.5 秒来一个
CALL_COST = 0.4              # 单次下游调用耗时（秒）
OUTAGE = (4.0, 13.0)         # 下游在这段时间内全挂


def dep_up(t: float) -> bool:
    return not (OUTAGE[0] <= t < OUTAGE[1])


# ---------------------------------------------------------------- 策略 A：不重试
def strategy_no_retry() -> dict:
    ok = fail = 0
    upstream_calls = 0
    latencies: list[float] = []
    for i in range(TOTAL_REQUESTS):
        t = i * ARRIVE_EVERY
        upstream_calls += 1
        if dep_up(t):
            ok += 1
            latencies.append(CALL_COST)
        else:
            fail += 1
            latencies.append(CALL_COST)
    return {"name": "A 不重试", "ok": ok, "fail": fail,
            "calls": upstream_calls, "lat": latencies, "fallback": 0}


# ---------------------------------------------------------------- 策略 B：重试 3 次
def strategy_retry(max_retry: int = 3) -> dict:
    ok = fail = 0
    upstream_calls = 0
    latencies: list[float] = []
    for i in range(TOTAL_REQUESTS):
        t = i * ARRIVE_EVERY
        spent = 0.0
        for _ in range(max_retry + 1):
            upstream_calls += 1
            spent += CALL_COST
            if dep_up(t + spent - CALL_COST):
                ok += 1
                break
        else:
            fail += 1
        latencies.append(spent)
    return {"name": f"B 重试 {max_retry} 次", "ok": ok, "fail": fail,
            "calls": upstream_calls, "lat": latencies, "fallback": 0}


# ---------------------------------------------------------------- 策略 C：重试 + 熔断
class Breaker:
    """closed → open（连续失败 5 次）→ half_open（等 3 秒试 1 次）→ closed"""

    def __init__(self, threshold: int = 5, cooldown: float = 3.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.state = "closed"
        self.fails = 0
        self.opened_at = 0.0
        self.transitions: list[str] = []
        self.rejected = 0        # 被熔断挡掉、根本没打到下游的请求

    def allow(self, t: float) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if t - self.opened_at >= self.cooldown:
                self.state = "half_open"
                self.transitions.append(f"  t={t:>5.1f}s  open → half_open（冷却结束，放 1 个探针）")
                return True
            self.rejected += 1
            return False
        return True      # half_open：只放探针

    def record(self, t: float, success: bool) -> None:
        if success:
            if self.state == "half_open":
                self.state = "closed"
                self.fails = 0
                self.transitions.append(f"  t={t:>5.1f}s  half_open → closed（探针成功，恢复）")
            self.fails = 0
            return
        self.fails += 1
        if self.state == "half_open":
            self.state = "open"
            self.opened_at = t
            self.transitions.append(f"  t={t:>5.1f}s  half_open → open（探针失败，继续挡）")
        elif self.state == "closed" and self.fails >= self.threshold:
            self.state = "open"
            self.opened_at = t
            self.transitions.append(f"  t={t:>5.1f}s  closed → open（连续 {self.fails} 次失败，停止放行）")


def strategy_breaker(max_retry: int = 2) -> dict:
    breaker = Breaker()
    ok = fail = 0
    fallback = 0
    upstream_calls = 0
    latencies: list[float] = []
    for i in range(TOTAL_REQUESTS):
        t = i * ARRIVE_EVERY
        spent = 0.0
        served = False
        for _ in range(max_retry + 1):
            if not breaker.allow(t + spent):
                break                      # 被熔断挡住：立刻走降级，不占下游资源
            upstream_calls += 1
            spent += CALL_COST
            good = dep_up(t + spent - CALL_COST)
            breaker.record(t + spent - CALL_COST, good)
            if good:
                ok += 1
                served = True
                break
        if not served:
            fail += 1
            if breaker.state == "open":
                fallback += 1              # 熔断期间：给缓存/兜底文案，用户至少不是白等
            spent += 0.01
        latencies.append(spent)
    return {"name": "C 重试+熔断+降级", "ok": ok, "fail": fail,
            "calls": upstream_calls, "lat": latencies, "fallback": fallback,
            "_breaker": breaker}


# ---------------------------------------------------------------- 跑
def p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * 0.95))]


print("=" * 74)
print("故障现场：下游服务在 t=4.0s 到 t=13.0s 之间完全不可用（9 秒）")
print(f"         40 个用户请求，每 0.5 秒来一个；单次调用耗时 {CALL_COST}s")
print("=" * 74)

results = [strategy_no_retry(), strategy_retry(3), strategy_breaker(2)]

print(f"\n{'策略':<16}{'成功':>5}{'失败':>5}{'打到下游':>9}{'P95':>8}{'降级兜底':>9}")
print("-" * 62)
for r in results:
    print(f"{r['name']:<16}{r['ok']:>5}{r['fail']:>5}{r['calls']:>9}"
          f"{p95(r['lat']):>7.2f}s{r['fallback']:>9}")

print("\n读法（三列要一起看，只看成功率会选错）：")
print("  · B 的成功率最高 —— 因为它用 3 倍流量去撞一堵正在倒的墙，把恢复期的运气捞回来了")
print("  · B 打到下游 93 次，是 A 的 2.3 倍。如果下游不是「挂了 9 秒」，而是「本来就快满了」，")
print("    这 3 倍流量会直接把雪崩从一次变成一场")
print("  · C 的成功率比 B 低一点，但它只让下游承 27 次调用，并且 19 个用户 0.4 秒内拿到了兜底")
print("  · C 的 P95 是 0.81s：熔断挡住的请求不排队、不重试，用户不用等")
print("\n  一句话：重试是「希望它活过来」，熔断是「先别让它死透」。生产系统两个都要，但顺序是熔断在前。")

b = results[2]["_breaker"]
print("\n熔断器状态迁移：")
for line in b.transitions:
    print(line)
print(f"  故障期间被熔断拦下（没打到下游）的请求：{b.rejected} 个")
print("\n如果没有熔断，这 {} 个请求会全部变成下游的重试流量。".format(b.rejected))

print("\n" + "=" * 74)
print("产品经理要定的三件事")
print("=" * 74)
print("1. 熔断阈值：连续失败几次算「坏了」？（5 次 / 或错误率 > 50% 持续 30 秒）")
print("2. 冷却时间：挡多久再试探？（3–10 秒；太短等于没挡）")
print("3. 降级文案：挡住了以后跟用户说什么？")
print()
print("   坏：「系统繁忙，请稍后重试。」← 让用户去撞，等于把压力还给用户")
print("   好：「这个问题我先给你一个大概方向：……（离线知识）。")
print("        需要精确结果的话，我 30 秒后帮你再查一次。」")
print()
print("   降级不是失败，是**换一种方式把事办了**。这条写不进代码，只能写进 PRD。")
