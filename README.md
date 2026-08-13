# GMGN V/L Radar Backup

Private backup for the Hermes `gmgn-dlmm-radar` no-agent cron.

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
