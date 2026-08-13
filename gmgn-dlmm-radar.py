#!/usr/bin/env python3
"""GMGN DLMM radar -> sends table straight to Telegram via Bot API (no wrapper)."""
import json, subprocess, os, sys, time
import urllib.request, urllib.parse
from pathlib import Path

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
CHAIN = "sol"
LIMIT = 100

# Exact GMGN UI filter supplied by the user. Ranking is 1h volume descending.
TREND_CMD = (
    "gmgn-cli market trending --chain sol --interval 1h --limit 100 "
    "--order-by volume --direction desc "
    "--filter has_social --filter not_wash_trading "
    "--min-liquidity 2500 --min-holder-count 200 --min-created 1h "
    "--min-gas-fee 20 --min-smart-degen-count 2 --min-swaps 1500 "
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
    """Return (5m run-rate / rolling 1h volume, display label)."""
    address = t.get("address")
    chain = t.get("chain")
    vol_1h = float(t.get("volume") or 0)
    if not address or not chain or vol_1h <= 0:
        return None, "-"
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
            return None, "-"
        vol_5m = sum(float(c.get("volume") or 0) for c in candles)
        ratio = (vol_5m * 12) / vol_1h
        if ratio > 1.20:
            icon = "🔥"
        elif ratio >= 0.80:
            icon = "🟢"
        elif ratio >= 0.50:
            icon = "🟡"
        else:
            icon = "🧊"
        return ratio, f"{icon}{ratio:.1f}"
    except Exception:
        return None, "-"

def build():
    from datetime import datetime, timezone, timedelta
    sol_hits = [t for t in gather(TREND_CMD) if safe_for_dlmm(t)]

    def rank_key(t):
        vol = float(t.get("volume") or 0)
        liq = float(t.get("liquidity") or 0)
        return (vol / liq if liq > 0 else 0, vol)

    sol_hits.sort(key=rank_key, reverse=True)
    bali = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%H:%M")
    lines = [f"GMGN V/L — {bali} Bali", ""]

    def money(v):
        v = float(v or 0)
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}k"
        return f"{v:.0f}"

    def add_section(title, hits):
        lines.append(title)
        lines.append(f"{'SYM':<8} {'VOL':>6} {'LIQ':>6} {'V/L':>5} {'FLOW':>6} {'SWAP':>5} {'MC':>6}")
        lines.append("-" * 50)
        if not hits:
            lines.append("kosong")
        for t in hits[:12]:
            sym = (t.get("symbol") or "?")[:8]
            vol_n = float(t.get('volume') or 0)
            liq_n = float(t.get('liquidity') or 0)
            vol = money(vol_n)
            liq = money(liq_n)
            vl = f"{vol_n/liq_n:.1f}" if liq_n > 0 else "-"
            _, flow = flow_5m(t)
            swaps = str(int(float(t.get('swaps') or 0)))
            mc = money(t.get('market_cap'))
            lines.append(f"{sym:<8} {vol:>6} {liq:>6} {vl:>5} {flow:>6} {swaps:>5} {mc:>6}")

    add_section("SOLANA", sol_hits)
    lines.extend([
        "",
        "V/L",
        "Volume 1h / liquidity.",
        "Makin tinggi = potensi fee makin cepat.",
        "Higher = faster potential fee velocity.",
        "",
        "FLOW",
        "🔥 panas   🟢 aktif   🟡 dingin   🧊 mati",
        "🔥 hot     🟢 active  🟡 cooling  🧊 cold",
        "",
        "ATURAN / RULE",
        "MAX HOLD 1 JAM / MAX HOLD 1 HOUR.",
        "Cuma get in, get out, lalu cari pool lain.",
        "Get in, get out, then rotate to next pool.",
        "EDGE KITA = ROTASI CEPAT / FAST ROTATION.",
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
