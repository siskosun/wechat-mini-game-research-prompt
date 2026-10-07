#!/usr/bin/env python3
"""Send one game-radar report to a Feishu custom bot webhook as plain text."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


MAX_CHARS = 4500
RETRIES = 3


def markdown_to_plain_text(text: str) -> str:
    """Remove common Markdown presentation syntax before Feishu delivery."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    plain_lines: list[str] = []
    for line in text.split("\n"):
        if re.fullmatch(r"\s*#{1,6}\s*", line):
            continue
        if re.fullmatch(r"\s*[-*_]{3,}\s*", line):
            continue
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "• ", line)
        line = re.sub(r"!\[([^\]]*)\]\((https?://[^)]+)\)", lambda m: f"图片：{m.group(2)}", line)
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", lambda m: f"{m.group(1)}：{m.group(2)}", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"__(.+?)__", r"\1", line)
        line = line.replace(chr(96), "")
        plain_lines.append(line.rstrip())
    plain = "\n".join(plain_lines)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip()


def split_text(text: str, limit: int = MAX_CHARS) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > limit:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(paragraph), limit):
                chunks.append(paragraph[start : start + limit])
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)
    return chunks


def gen_sign(secret: str, timestamp: int) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def send_once(webhook_url: str, signing_secret: str, text: str) -> None:
    timestamp = int(time.time())
    payload: dict[str, object] = {
        "msg_type": "text",
        "content": {"text": text},
    }
    if signing_secret:
        payload["timestamp"] = timestamp
        payload["sign"] = gen_sign(signing_secret, timestamp)

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "game-radar-github-actions/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="replace")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Feishu returned non-JSON response: {raw[:300]}") from exc

    code = result.get("code")
    status_code = result.get("StatusCode")
    if code not in (None, 0) or status_code not in (None, 0):
        message = result.get("msg") or result.get("StatusMessage") or str(result)
        raise RuntimeError(f"Feishu rejected message: {message}")


def send_with_retry(webhook_url: str, signing_secret: str, text: str) -> None:
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            send_once(webhook_url, signing_secret, text)
            return
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(2**attempt)
    raise RuntimeError(f"Feishu send failed after {RETRIES} attempts: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
    signing_secret = os.environ.get("FEISHU_SIGNING_SECRET", "").strip()

    if not webhook_url:
        print("FEISHU_WEBHOOK_URL is not configured.", file=sys.stderr)
        return 2
    if not args.report.is_file():
        print(f"Report not found: {args.report}", file=sys.stderr)
        return 2

    text = args.report.read_text(encoding="utf-8").strip()
    if not text:
        print(f"Report is empty: {args.report}", file=sys.stderr)
        return 2

    text = markdown_to_plain_text(text)
    chunks = split_text(text)
    date_label = args.report.stem

    for index, chunk in enumerate(chunks, start=1):
        prefix = f"【每日游戏雷达】{date_label}"
        if len(chunks) > 1:
            prefix += f"（{index}/{len(chunks)}）"
        send_with_retry(webhook_url, signing_secret, f"{prefix}\n\n{chunk}")

    print(f"Sent {args.report} in {len(chunks)} message(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
