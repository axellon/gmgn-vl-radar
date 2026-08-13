# GMGN V/L Radar Backup

Public backup for the Hermes `gmgn-dlmm-radar` no-agent cron.

## What it does

- Runs every 10 minutes through Hermes cron.
- Fetches GMGN trending candidates for Solana.
- Ranks each chain by rolling 1-hour `volume / liquidity` (V/L).
- Shows a compact `FLOW` signal: `(last 5m volume × 12) / rolling 1h volume`.
- Sends the report directly to Telegram, avoiding the Hermes cron wrapper.
- Uses no LLM tokens (`no_agent: true`).

## Current gates

### Solana

- interval: 1h
- liquidity >= $2,500
- holders >= 200
- age >= 1h
- gas fee >= 20
- smart degen >= 2
- swaps >= 1,500
- market cap >= $100,000
- has social
- not wash trading
- creator close is **not required**


## Secret setup

Secrets are intentionally excluded from Git. Create:

`~/.config/gmgn-dlmm-radar/telegram.env`

```env
TG_BOT_TOKEN=your_telegram_bot_token
TG_CHAT_ID=your_telegram_chat_id
RADAR_TIMEZONE=UTC
RADAR_LOCATION=UTC
```

Protect it:

```bash
chmod 600 ~/.config/gmgn-dlmm-radar/telegram.env
```

Timezone examples:

- Bali/WITA: `RADAR_TIMEZONE=Asia/Makassar`, `RADAR_LOCATION=Bali`
- Jakarta/WIB: `RADAR_TIMEZONE=Asia/Jakarta`, `RADAR_LOCATION=Jakarta`
- UTC: `RADAR_TIMEZONE=UTC`, `RADAR_LOCATION=UTC`
- New York: `RADAR_TIMEZONE=America/New_York`, `RADAR_LOCATION=New_York`

Use a valid IANA timezone name. If invalid, the script falls back to UTC.

GMGN CLI must already be configured separately via `gmgn-cli config`.

## Restore

```bash
./install.sh
```

The installer copies the sanitized script and filter config. Recreate the Hermes cron using `cron-manifest.json` as reference, or through Hermes with:

- schedule: `*/10 * * * *`
- script: `gmgn-dlmm-radar.py`
- no_agent: `true`
- delivery: `local`

## Example Telegram output

The actual candidates and values change every run:

```text
GMGN V/L — 20:01 Bali

SOLANA
SYM         VOL    LIQ   V/L   FLOW  SWAP     MC
--------------------------------------------------
App        573k    78k   7.3   🧊0.5  5657   815k
K-HOME     619k   337k   1.8   🧊0.4  4964   1.5M
BOIÚNA     105k    84k   1.3   🔥2.4  1674   704k
ORANGE      58k    87k   0.7   🧊0.1  2921   1.1M
Dealer      47k   153k   0.3   🔥1.2  1627   3.3M

V/L
Volume 1h / liquidity.
Makin tinggi = potensi fee makin cepat.
Higher = faster potential fee velocity.

FLOW
🔥 panas   🟢 aktif   🟡 dingin   🧊 mati
🔥 hot     🟢 active  🟡 cooling  🧊 cold

ATURAN / RULE
MAX HOLD 1 JAM / MAX HOLD 1 HOUR.
Cuma get in, get out, lalu cari pool lain.
Get in, get out, then rotate to next pool.
```

`FLOW` is calculated as `(last 5m volume × 12) / rolling 1h volume`:

- `🔥 > 1.20`: accelerating / makin panas
- `🟢 0.80–1.20`: active / aktif
- `🟡 0.50–0.79`: cooling / mulai dingin
- `🧊 < 0.50`: cold / dingin
