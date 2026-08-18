#!/usr/bin/env python3
"""Scan GMGN pools and send compact V/L and momentum boards to Telegram."""

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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
    "--min-marketcap 1000"
)

# Robinhood exposes the same GMGN metrics, but its gas-fee scale differs.
# Reusing Solana's min-gas-fee=20 gate hides active Robinhood runners.
# Robinhood small caps are thinner than Solana, so use lighter gates
# matching Base: holder 30, swap 300, liq 1K, no smart-degen gate.
ROBINHOOD_CMD = (
    "gmgn-cli market trending --chain robinhood --interval 1h --limit 100 "
    "--order-by volume --direction desc "
    "--min-liquidity 1000 --min-holder-count 30 --min-created 30m "
    "--min-swaps 300 --min-marketcap 1000 --max-marketcap 5000000"
)

# BSC and Base use the same GMGN metrics. Their gas-fee scale also differs
# from Solana, so skip the min-gas-fee gate the same way as Robinhood.
BASE_CMD = (
    "gmgn-cli market trending --chain base --interval 1h --limit 100 "
    "--order-by volume --direction desc "
    "--min-liquidity 1000 --min-holder-count 30 --min-created 30m "
    "--min-swaps 300 --min-marketcap 1000 --max-marketcap 5000000"
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
    """Reject rows that GMGN explicitly marks as wash trading."""
    return t.get("is_wash_trading") is not True


def token_price_data(t):
    """Fetch one exact token snapshot for swap/volume acceleration metrics."""
    address = t.get("address")
    chain = t.get("chain")
    if not address or not chain:
        return None
    cmd = [
        "gmgn-cli", "token", "info", "--chain", chain,
        "--address", address, "--raw",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25).stdout
        data = json.loads(out)
        # Keep both the price block (flow metrics) and wallet_tags_stat (smart cluster).
        price = data.get("price", data) if isinstance(data, dict) else {}
        if isinstance(data, dict):
            price["wallet_tags_stat"] = data.get("wallet_tags_stat", {})
            price["stat"] = data.get("stat", {})
        return price if isinstance(price, dict) else None
    except Exception:
        return None


def token_price_map(hits):
    """Fetch exact snapshots for the full eligible universe with bounded concurrency."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        snapshots = list(pool.map(token_price_data, hits))
    return {
        (t.get("chain"), t.get("address")): snapshot
        for t, snapshot in zip(hits, snapshots)
        if t.get("chain") and t.get("address") and snapshot
    }


def flow_5m(t, price_data=None):
    """Return volume FLOW plus five-minute swap acceleration.

    Computed from the exact token snapshot only (no extra kline call):
    FLOW = (volume_5m × 12) / volume_1h and direction from 5m buy/sell volume.
    """
    address = t.get("address")
    chain = t.get("chain")
    vol_1h = float(t.get("volume") or 0)
    if not address or not chain or vol_1h <= 0:
        return None, "-", 0, 0, None

    # Reuse the full-universe snapshot collected once per build.
    price_data = price_data or token_price_data(t) or {}
    if not price_data:
        return None, "-", 0, 0, None

    vol_5m = float(price_data.get("volume_5m") or 0)
    if vol_5m <= 0:
        return None, "-", 0, 0, None
    ratio = (vol_5m * 12) / vol_1h

    buy_vol_5m = float(price_data.get("buy_volume_5m") or 0)
    sell_vol_5m = float(price_data.get("sell_volume_5m") or 0)
    swaps_5m = int(float(price_data.get("swaps_5m") or 0))
    swaps_1h = float(price_data.get("swaps_1h") or t.get("swaps") or 0)
    swap_speed = (swaps_5m * 12 / swaps_1h) if swaps_1h > 0 else None

    # Direction from 5m buy/sell volume. A 5% margin prevents tiny
    # differences from being mislabeled directional.
    if buy_vol_5m > sell_vol_5m * 1.05:
        direction = "📈"
    elif sell_vol_5m > buy_vol_5m * 1.05:
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

def load_config():
    """Read chain toggles + interval from chains.json (repo-friendly config)."""
    cfg_path = Path(__file__).resolve().parent / "chains.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text())
        except Exception:
            pass
    return {"interval_min": 10, "chains": []}

def build():
    from datetime import datetime, timezone
    cfg = load_config()
    active = [c for c in cfg.get("chains", []) if c.get("enabled")]
    if not active:
        active = [{"title": "SOLANA", "chain": "sol",
                   "extra_gates": "--min-marketcap 1000"}]

    # Build one trending command per enabled chain.
    base = "gmgn-cli market trending --chain {c} --interval 1h --limit {lim} " \
           "--order-by volume --direction desc {gates}"
    chain_hits = {}
    for ch in active:
        chain = ch["chain"]
        gates = ch.get("extra_gates", "")
        cmd = base.format(c=chain, lim=LIMIT, gates=gates)
        chain_hits[ch["title"]] = [t for t in gather(cmd) if safe_for_dlmm(t)]

    # Fetch snapshots for a wider candidate pool so we can rank by V/L.
    pool = []
    for hits in chain_hits.values():
        pool.extend(hits[:25])
    price_by_address = token_price_map(pool)

    def snapshot_for(t):
        return price_by_address.get((t.get("chain"), t.get("address")))

    def rank_key(t):
        vol = float(t.get("volume") or 0)
        liq = float(t.get("liquidity") or 0)
        return (vol / liq if liq > 0 else 0, vol)

    for title in chain_hits:
        chain_hits[title].sort(key=rank_key, reverse=True)

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

    def add_section(title, hits, hot_alert=False):
        lines.append(title)
        # FLOW stays last because Telegram renders emoji at inconsistent widths.
        # Keeping text-only columns before it preserves mobile alignment.
        lines.append(f"{'SYM':<7} {'V/L':>4} {'S1H':>5} {'S5M':>4} {'S×':>4} {'MC':>5}  {'FLOW':>5}")
        lines.append("-" * 44)
        if not hits:
            lines.append("none")
        for t in hits[:5]:
            sym = (t.get("symbol") or "?")[:7]
            vol_n = float(t.get('volume') or 0)
            liq_n = float(t.get('liquidity') or 0)
            vl = f"{vol_n/liq_n:.1f}" if liq_n > 0 else "-"
            _, flow, swaps_1h, swaps_5m, swap_speed = flow_5m(
                t, snapshot_for(t)
            )
            speed = f"{swap_speed:.1f}" if swap_speed is not None else "-"
            mc = money(t.get('market_cap'))
            lines.append(f"{sym:<7} {vl:>4} {swaps_1h:>5} {swaps_5m:>4} {speed:>4} {mc:>5}  {flow:>5}")

    # Render each enabled chain, then HOT POOL after the first section.
    first = True
    for ch in active:
        title = ch["title"]
        add_section(title, chain_hits[title])
        lines.append("")
        if first:
            first = False
            # Hot Pool Alert: tokens with >=1000 swaps in 5m on this chain.
            hot = []
            for t in chain_hits[title]:
                snap = snapshot_for(t) or {}
                s5m = int(float(snap.get("swaps_5m") or t.get("swaps_5m") or 0))
                if s5m >= 1000:
                    hot.append((t.get("symbol") or "?", s5m))
            if hot:
                lines.append("HOT POOL")
                for sym, s5m in hot:
                    lines.append(f"🔥 Hot Pool Alert {sym[:7]}🚨 (S5M {s5m})")
                lines.append("")

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
        "CMDS",
        "/sol /rh /base /all  set chains",
        "/5 /10 /30  set interval min",
        "/run  build+send now",
        "",
        "RULE",
        "MAX HOLD 1 HOUR.",
        "Get in, get out, then rotate to next pool.",
    ])
    return "```\n" + "\n".join(lines) + "\n```"

CONFIG_PATH = Path(__file__).resolve().parent / "chains.json"

def handle_cmd(argv):
    """Edit chains.json from slash-style CLI commands (no LLM needed)."""
    if not argv:
        return None
    cfg_path = CONFIG_PATH
    cfg = load_config() if cfg_path.exists() else {"interval_min": 10, "chains": []}
    known = {
        "sol": ("SOLANA", "--filter has_social --filter not_wash_trading --min-gas-fee 20 --min-smart-degen-count 2 --min-swaps 500 --min-marketcap 1000"),
        "robinhood": ("ROBINHOOD", "--min-swaps 300 --min-marketcap 1000 --max-marketcap 5000000"),
        "base": ("BASE", "--min-swaps 300 --min-marketcap 1000 --max-marketcap 5000000"),
    }
    def _set(ch, on):
        title, gates = known[ch]
        for c in cfg["chains"]:
            if c["chain"] == ch:
                c["enabled"] = on
                return
        cfg["chains"].append({"enabled": on, "title": title, "chain": ch, "extra_gates": gates})

    changed = False
    for a in argv:
        a = a.lstrip("/").lower()
        if a in known:
            # A single chain command enables that chain and disables the rest.
            for ch in known:
                _set(ch, ch == a)
            changed = True
        elif a == "all":
            for ch in known:
                _set(ch, True)
            changed = True
        elif a.isdigit():
            cfg["interval_min"] = int(a); changed = True

    if changed:
        cfg_path.write_text(json.dumps(cfg, indent=2))
        print(f"config updated: interval={cfg['interval_min']}m chains=" +
              ",".join(c["chain"] for c in cfg["chains"] if c["enabled"]))
    return cfg

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
    args = sys.argv[1:]
    if args and "/run" not in args:
        # Config-only command: edit chains.json, no board sent.
        handle_cmd(args)
        sys.exit(0)
    msg = build()
    cid = get_chat_id()
    if not cid:
        # fallback: just print so cron/local still shows something
        print(msg)
        print("[no chat_id yet - chat the bot once]", file=sys.stderr)
        sys.exit(0)
    res = send(msg, cid)
    print("sent" if res.get("ok") else f"fail {res}")
