#!/usr/bin/env python3
"""Scan Solana pools and send a compact V/L report to Telegram."""

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def load_private_env():
    env_path = Path.home() / ".config/gmgn-dlmm-radar/telegram.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

load_private_env()
TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TG_CHAT_ID", "")
RADAR_TIMEZONE = os.environ.get("RADAR_TIMEZONE", "UTC")
RADAR_LOCATION = os.environ.get("RADAR_LOCATION", RADAR_TIMEZONE)
CHAIN = "sol"
LIMIT = 100


# GMGN Trending provides the candidate set. Ranking happens locally by V/L.
TREND_CMD = (
    "gmgn-cli market trending --chain sol --interval 1h --limit 100 "
    "--order-by volume --direction desc "
    "--filter has_social --filter not_wash_trading "
    "--min-liquidity 2500 --min-holder-count 200 --min-created 30m "
    "--min-gas-fee 20 --min-smart-degen-count 2 --min-swaps 500 "
    "--min-marketcap 100000"
)


def run(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout
        return json.loads(out)
    except Exception:
        return {}

def gather(cmd=TREND_CMD):
    tr = run(cmd)
    if isinstance(tr, dict):
        rank = tr.get("data", {}).get("rank", [])
        if isinstance(rank, list):
            return rank
    return []

def safe_for_dlmm(t):
    """Solana safety gate: reject detected wash trading only."""
    return t.get("is_wash_trading") is not True


def flow_5m(t):
    """Return volume FLOW plus five-minute swap acceleration."""
    address = t.get("address")
    chain = t.get("chain")
    vol_1h = float(t.get("volume") or 0)
    if not address or not chain or vol_1h <= 0:
        return None, "-", 0, 0, None
    now = int(time.time())
    cmd = [
        "gmgn-cli", "market", "kline", "--chain", chain,
        "--address", address, "--resolution", "1m",
        "--from", str(now - 480), "--to", str(now), "--raw",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25).stdout
        candles = json.loads(out).get("list", [])[-5:]
        if not candles:
            return None, "-", 0, 0, None
        vol_5m = sum(float(c.get("volume") or 0) for c in candles)
        ratio = (vol_5m * 12) / vol_1h
        open_5m = float(candles[0].get("open") or 0)
        close_5m = float(candles[-1].get("close") or 0)
        price_change_5m = ((close_5m / open_5m) - 1) if open_5m > 0 else 0

        # Fetch exact five-minute directional volume and swap counts.
        info_cmd = [
            "gmgn-cli", "token", "info", "--chain", chain,
            "--address", address, "--raw",
        ]
        info_out = subprocess.run(
            info_cmd, capture_output=True, text=True, timeout=25
        ).stdout
        price_data = json.loads(info_out).get("price", {})
        buy_vol_5m = float(price_data.get("buy_volume_5m") or 0)
        sell_vol_5m = float(price_data.get("sell_volume_5m") or 0)
        swaps_5m = int(float(price_data.get("swaps_5m") or 0))
        swaps_1h = float(price_data.get("swaps_1h") or t.get("swaps") or 0)
        swap_speed = (swaps_5m * 12 / swaps_1h) if swaps_1h > 0 else None

        # Require price and directional volume to agree. A 5% margin prevents
        # tiny buy/sell differences from being mislabeled directional.
        if price_change_5m > 0.01 and buy_vol_5m > sell_vol_5m * 1.05:
            direction = "📈"
        elif price_change_5m < -0.01 and sell_vol_5m > buy_vol_5m * 1.05:
            direction = "📉"
        else:
            direction = "🔄"

        if ratio > 1.20:
            icon = "🔥"
        elif ratio >= 0.80:
            icon = "🟢"
        elif ratio >= 0.50:
            icon = "🟡"
        else:
            icon = "🧊"
        return ratio, f"{icon}{direction}{ratio:.1f}", int(swaps_1h), swaps_5m, swap_speed
    except Exception:
        return None, "-", 0, 0, None

def build():
    from datetime import datetime, timezone
    sol_hits = [t for t in gather(TREND_CMD) if safe_for_dlmm(t)]

    def rank_key(t):
        vol = float(t.get("volume") or 0)
        liq = float(t.get("liquidity") or 0)
        return (vol / liq if liq > 0 else 0, vol)

    sol_hits.sort(key=rank_key, reverse=True)

    try:
        local_tz = ZoneInfo(RADAR_TIMEZONE)
    except ZoneInfoNotFoundError:
        local_tz = timezone.utc
    local_time = datetime.now(local_tz).strftime("%H:%M")
    lines = [f"GMGN V/L — {local_time} {RADAR_LOCATION}", ""]

    def money(v):
        v = float(v or 0)
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}k"
        return f"{v:.0f}"

    def add_section(title, hits):
        lines.append(title)
        # FLOW stays last because Telegram renders emoji at inconsistent widths.
        # Keeping text-only columns before it preserves mobile alignment.
        lines.append(f"{'SYM':<7} {'V/L':>4} {'S1H':>5} {'S5M':>4} {'S×':>4} {'MC':>5}  {'FLOW':>5}")
        lines.append("-" * 44)
        if not hits:
            lines.append("none")
        for t in hits[:12]:
            sym = (t.get("symbol") or "?")[:7]
            vol_n = float(t.get('volume') or 0)
            liq_n = float(t.get('liquidity') or 0)
            vl = f"{vol_n/liq_n:.1f}" if liq_n > 0 else "-"
            _, flow, swaps_1h, swaps_5m, swap_speed = flow_5m(t)
            speed = f"{swap_speed:.1f}" if swap_speed is not None else "-"
            mc = money(t.get('market_cap'))
            lines.append(f"{sym:<7} {vl:>4} {swaps_1h:>5} {swaps_5m:>4} {speed:>4} {mc:>5}  {flow:>5}")
            lines.append("")

        # Remove the trailing blank after the last token.
        if hits and lines[-1] == "":
            lines.pop()

    add_section("SOLANA", sol_hits)
    lines.extend([
        "",
        "V/L",
        "1h volume / liquidity.",
        "Higher = faster potential fee velocity.",
        "",
        "S×",
        "(5m swaps × 12) / rolling 1h swaps.",
        "≥1.3 accelerating   ≥2.0 explosive",
        "",
        "FLOW",
        "🔥 hot   🟢 active   🟡 cooling   🧊 cold",
        "📈 bullish  📉 bearish  🔄 mixed/chop",
        "",
        "RULE",
        "MAX HOLD 1 HOUR.",
        "Get in, get out, then rotate to next pool.",
    ])
    return "```\n" + "\n".join(lines) + "\n```"

def get_chat_id():
    if CHAT_ID:
        return CHAT_ID
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    with urllib.request.urlopen(url, timeout=15) as r:
        d = json.load(r)
    for u in reversed(d.get("result", [])):
        chat = u.get("message", {}).get("chat", {})
        if chat.get("id"):
            return str(chat["id"])
    return ""

def send(text, chat_id):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

if __name__ == "__main__":
    msg = build()
    cid = get_chat_id()
    if not cid:
        # fallback: just print so cron/local still shows something
        print(msg)
        print("[no chat_id yet - chat the bot once]", file=sys.stderr)
        sys.exit(0)
    res = send(msg, cid)
    print("sent" if res.get("ok") else f"fail {res}")
