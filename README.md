# GMGN V/L Radar

A small Solana pool scanner built around GMGN market data. It ranks active pools by hourly volume relative to liquidity, adds a short-term flow reading, and posts the result to Telegram.

The script is meant for quick DLMM rotation. It does not place trades or touch a wallet.

## How it works

The candidate list comes from GMGN Trending on Solana. Pools are ranked by:

```text
V/L = rolling 1h volume / liquidity
```

`FLOW` compares the latest five minutes with the rolling one-hour volume:

```text
FLOW = (latest 5m volume * 12) / rolling 1h volume
```

The arrow adds direction from the same five-minute window:

- `📈` price up and buy volume leads
- `📉` price down and sell volume leads
- `🔄` mixed or conflicting flow

Speed labels:

- `🔥` above 1.20
- `🟢` 0.80 to 1.20
- `🟡` 0.50 to 0.79
- `🧊` below 0.50

A hot reading measures activity, not safety. `🔥📉` usually means an active sell-off.

## Filters

The default Solana scan uses:

| Filter | Value |
| --- | ---: |
| Interval | 1h |
| Minimum liquidity | $2,500 |
| Minimum holders | 200 |
| Minimum age | 1h |
| Minimum gas fee | 20 |
| Minimum smart degen count | 2 |
| Minimum swaps | 1,500 |
| Minimum market cap | $100,000 |
| Social profile | Required |
| Wash trading | Excluded |
| Creator close | Not required |

## Requirements

- Python 3.9 or newer
- [GMGN CLI](https://www.npmjs.com/package/gmgn-cli), configured with access to market commands
- Hermes Agent for the included scheduled-job setup
- A Telegram bot token and target chat ID

## Install

```bash
git clone https://github.com/ayehuasca/gmgn-vl-radar.git
cd gmgn-vl-radar
./install.sh
```

Configure GMGN CLI separately, then edit:

```text
~/.config/gmgn-dlmm-radar/telegram.env
```

```env
TG_BOT_TOKEN=your_bot_token
TG_CHAT_ID=your_chat_id
RADAR_TIMEZONE=UTC
RADAR_LOCATION=UTC
```

The timezone uses an IANA name. Examples:

| Location | `RADAR_TIMEZONE` | `RADAR_LOCATION` |
| --- | --- | --- |
| Bali | `Asia/Makassar` | `Bali` |
| Jakarta | `Asia/Jakarta` | `Jakarta` |
| New York | `America/New_York` | `New York` |
| UTC | `UTC` | `UTC` |

The installer creates the env file with mode `600`. The real credentials stay outside the repository.

## Run it

Send one report immediately:

```bash
python3 ~/.hermes/scripts/gmgn-dlmm-radar.py
```

The included cron config runs every ten minutes with `no_agent: true`. The script sends directly to Telegram, so Hermes delivery remains local:

```json
{
  "name": "gmgn-dlmm-radar",
  "schedule": "*/10 * * * *",
  "script": "gmgn-dlmm-radar.py",
  "no_agent": true,
  "deliver": "local"
}
```

Use `config/cron.json` when creating the scheduled job.

## Output

```text
GMGN V/L — 20:01 Bali

SOLANA
SYM       VOL   LIQ  V/L   FLOW  SWP   MC
-----------------------------------------
App      573k   78k  7.3  🧊🔄0.5 5657 815k

K-HOME   619k  337k  1.8  🔥📉2.4 4964 1.5M

BOIÚNA   105k   84k  1.3  🔥📈1.6 1674 704k

V/L
1h volume / liquidity.
Higher = faster potential fee velocity.

FLOW
🔥 hot   🟢 active   🟡 cooling   🧊 cold
📈 bullish  📉 bearish  🔄 mixed/chop

RULE
MAX HOLD 1 HOUR.
Get in, get out, then rotate to next pool.
```

## Files

```text
src/gmgn-dlmm-radar.py   scanner and Telegram sender
config/filter-query.json GMGN filter reference
config/cron.json         scheduled-job settings
telegram.env.example     environment template
install.sh               local installer
```

## Notes

- The report is a scanner, not an execution system.
- FLOW is a five-minute signal against a one-hour baseline. A ten-minute schedule means a delivered message can age before the next run.
- Token symbols are display-only. Use the token address before acting on a result.
- Maximum hold is an operating rule for this setup, not a guarantee of profit.
