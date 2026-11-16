#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库自检：Markdown 内链、讲义结构、demo 冒烟。

    python scripts/check.py

三件事，任何一件不过就退出码 1：
1. 所有 Markdown 里的相对链接都指向真实存在的文件（改了文件名最容易漏这里）
2. 每一讲都还带着「一句话结论 / 90 秒话术 / 练习」这三节（结构是这门课的产品承诺）
3. README 提到了每一讲，没有讲被漏收进目录
4. demo 只 import 标准库，并且都能跑通、真的打印了东西

不需要装任何第三方库。CI 里跑的也是这一个文件，本地和线上不会出现两套标准。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import ast
import pathlib
from urllib.parse import unquote

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK，中文会炸

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", "__pycache__", "node_modules"}

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+?)\)")
DEMO_RE = re.compile(r"demos/([0-9a-z_]+\.py)")
REQUIRED_SECTIONS = ("一句话结论", "90 秒", "练习")
LECTURE_RE = re.compile(r"^(\d{2})-.+\.md$")

problems: list[str] = []
checked_links = 0
checked_lectures = 0
checked_demos = 0


def md_files() -> list[pathlib.Path]:
    out = []
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        out.append(p)
    return out


def check_links(files: list[pathlib.Path]) -> None:
    global checked_links
    for f in files:
        text = f.read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            target = raw.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if target.startswith("//"):
                continue
            path_part = unquote(target.split("#", 1)[0])
            if not path_part:
                continue
            checked_links += 1
            resolved = (f.parent / path_part).resolve()
            if not resolved.exists():
                rel = f.relative_to(ROOT)
                problems.append(f"断链  {rel}  ->  {target}")


def check_lectures(files: list[pathlib.Path]) -> None:
    global checked_lectures
    numbered: dict[int, pathlib.Path] = {}
    for f in files:
        m = LECTURE_RE.match(f.name)
        if not m:
            continue
        if f.parent == ROOT:  # 根目录的 README / SOURCES 不算讲义
            continue
        numbered[int(m.group(1))] = f

    for num, f in sorted(numbered.items()):
        checked_lectures += 1
        text = f.read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            if section not in text:
                problems.append(f"缺小节  {f.relative_to(ROOT)}  没有「{section}」")

    # 02–15 是正文 14 讲，少一讲说明文件被误删或误改名
    body = [n for n in numbered if n >= 2]
    if len(body) != 14:
        problems.append(f"讲数不对  正文应有 14 讲，实际 {len(body)} 讲：{sorted(body)}")


def check_readme_covers_lectures(files: list[pathlib.Path]) -> None:
    readme = ROOT / "README.md"
    if not readme.exists():
        problems.append("缺少 README.md")
        return
    text = readme.read_text(encoding="utf-8")
    for f in files:
        if f.parent == ROOT or not LECTURE_RE.match(f.name):
            continue
        rel = f.relative_to(ROOT).as_posix()
        if rel not in text:
            problems.append(f"目录漏收  README 里没有 {rel}")


def check_demos(files: list[pathlib.Path]) -> None:
    global checked_demos
    demos_dir = ROOT / "demos"
    if not demos_dir.is_dir():
        problems.append("缺少 demos/ 目录")
        return

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    scripts = sorted(p for p in demos_dir.glob("*.py") if p.name != "fake_llm.py")
    for script in scripts:
        checked_demos += 1
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                env=env,
            )
        except subprocess.TimeoutExpired:
            problems.append(f"跑不完  {script.name}  超过 180 秒")
            continue
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip().splitlines()[-3:]
            if not detail:
                detail = ["（stderr 为空，错误可能打在 stdout 末尾）"] + (proc.stdout or "").strip().splitlines()[-2:]
            problems.append(
                f"退出码 {proc.returncode}  {script.name}\n        " + "\n        ".join(detail)
            )
        elif not (proc.stdout or "").strip():
            problems.append(f"没输出  {script.name}  退出码 0 但什么都没打印")

    # README / demos/README 里提到的 demo 必须真实存在
    mentioned = set()
    for f in files:
        mentioned.update(DEMO_RE.findall(f.read_text(encoding="utf-8")))
    for name in sorted(mentioned):
        if not (demos_dir / name).exists():
            problems.append(f"提到不存在的 demo  demos/{name}")


def check_stdlib_only(files: list[pathlib.Path]) -> None:
    """demo 的卖点是「不装任何第三方库」，所以这里把 import 也管住。

    一旦有人图省事写了 import requests / from openai import OpenAI，
    本课就从一个「离线可跑的证据」退化成「先配环境的作业」。
    """
    demos_dir = ROOT / "demos"
    if not demos_dir.is_dir():
        return
    local = {p.stem for p in demos_dir.glob("*.py")}
    allowed = set(sys.stdlib_module_names) | local
    for path in sorted(demos_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name and name not in allowed:
                    problems.append(f"第三方依赖  demos/{path.name}  import {name}")


def main() -> int:
    files = md_files()
    check_links(files)
    check_lectures(files)
    check_readme_covers_lectures(files)
    check_stdlib_only(files)
    check_demos(files)

    print(f"Markdown {len(files)} 个 · 内链 {checked_links} 条 · 讲义 {checked_lectures} 讲 · demo {checked_demos} 个")
    if problems:
        print(f"\n发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
