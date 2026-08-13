# GMGN V/L Radar Backup

Private backup for the Hermes `gmgn-dlmm-radar` no-agent cron.

## What it does

- Runs every 10 minutes through Hermes cron.
- Fetches GMGN trending candidates for Solana and Robinhood Chain.
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

### Robinhood Chain

- interval: 1h
- liquidity >= $1,000
- holders >= 200
- age >= 1h
- gas fee >= 20
- smart degen >= 3
- swaps >= 500
- market cap >= $100,000
- has social
- not wash trading
- creator close required

## Secret setup

Secrets are intentionally excluded from Git. Create:

`~/.config/gmgn-dlmm-radar/telegram.env`

```env
TG_BOT_TOKEN=your_telegram_bot_token
TG_CHAT_ID=your_telegram_chat_id
```

Protect it:

```bash
chmod 600 ~/.config/gmgn-dlmm-radar/telegram.env
```

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
