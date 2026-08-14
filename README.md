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

## Run locally without a VPS

You do not need a VPS. Install Hermes Agent on Windows through WSL, or on a Linux or macOS computer, and run the radar locally with Telegram.

The setup is simple:

1. Install [Hermes Agent](https://hermes-agent.nousresearch.com/docs/).
2. Install and configure GMGN CLI.
3. Clone this repository and run `./install.sh`.
4. Add your Telegram bot token and chat ID.
5. Test the radar once, then add the Hermes cron.

Your computer must stay turned on and connected to the internet for scheduled reports to keep running.

The radar sends reports straight to Telegram every five minutes. Hermes only handles the schedule. The cron uses `no_agent: true`, so it does not call an AI model or spend LLM tokens while running.

Any inexpensive model is fine for the initial Hermes setup because the radar cron does not use it.

## Install

### 1. Install the radar

```bash
git clone https://github.com/ayehuasca/gmgn-vl-radar.git
cd gmgn-vl-radar
./install.sh
```

### 2. Set up GMGN API access

Install GMGN CLI if it is not already available:

```bash
npm install -g gmgn-cli
```

Start the API setup:

```bash
gmgn-cli config
```

The command prints a GMGN API Key creation link. Open that link in a browser, sign in to GMGN, and create an API key. Copy the key, then apply it locally:

```bash
gmgn-cli config --apply YOUR_GMGN_API_KEY
```

Check the setup:

```bash
gmgn-cli config --check
```

A successful check exits without an error. You can also test the market endpoint:

```bash
gmgn-cli market trending \
  --chain sol \
  --interval 1h \
  --limit 5
```

GMGN CLI writes the API key and its generated private key to:

```text
~/.config/gmgn/.env
```

Do not copy that file into this repository. Do not paste the API key into `src/gmgn-dlmm-radar.py`. The script calls GMGN CLI, and GMGN CLI reads the credentials from `~/.config/gmgn/.env` automatically.

If `gmgn-cli config --check` fails:

- `gmgn-cli: command not found`: run `npm install -g gmgn-cli` again.
- `401` or `403`: confirm the key with `gmgn-cli config --apply YOUR_GMGN_API_KEY`. GMGN market commands require IPv4, so disable outbound IPv6 if the key is valid but access is still rejected.
- `429`: wait for the rate limit to reset before retrying.

### 3. Set up Telegram

Edit:

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

The included cron config runs every five minutes with `no_agent: true`. The script sends directly to Telegram, so Hermes delivery remains local:

```json
{
  "name": "gmgn-dlmm-radar",
  "schedule": "*/5 * * * *",
  "script": "gmgn-dlmm-radar.py",
  "no_agent": true,
  "deliver": "local"
}
```

Use `config/cron.json` when creating the scheduled job.

## Latest radar update

The compact table now focuses on recent activity instead of showing raw volume and liquidity columns:

- The minimum token age was reduced from one hour to 30 minutes.
- The rolling one-hour swap gate was reduced from 1,500 to 500 swaps.
- These two discovery changes allow younger accelerating pools to enter the radar before their early activity cools down. All other eligibility gates and the one-hour `V/L` ranking stay unchanged.
- `S1H` shows total swaps during the rolling one-hour window.
- `S5M` shows swaps during the latest five minutes.
- `S×` compares current five-minute swap speed with the one-hour baseline.
- `FLOW` still measures five-minute volume speed and direction.
- `VOL` and `LIQ` were removed from the display to keep the report readable on a phone. Liquidity is still used by the minimum-liquidity gate and as the denominator in `V/L`.

The broader gates increase coverage, not certainty. Use `S×` together with `FLOW` to separate an accelerating bullish pool from bot churn or a fast sell-off.

## Output

```text
GMGN V/L — 07:48 Bali

SOLANA
SYM      V/L   S1H  S5M   S×    MC   FLOW
--------------------------------------------
PLANSEM 12.7  5622  478  1.0  1.6M  🟢📉0.8

cc       5.8  5590  427  0.9  1.4M  🟡📉0.8

BOB      2.2  1652  266  1.9  235k  🔥📉2.4

V/L
1h volume / liquidity.
Higher = faster potential fee velocity.

S×
(5m swaps × 12) / rolling 1h swaps.
≥1.3 accelerating   ≥2.0 explosive

FLOW
🔥 hot   🟢 active   🟡 cooling   🧊 cold
📈 bullish  📉 bearish  🔄 mixed/chop

RULE
MAX HOLD 1 HOUR.
Get in, get out, then rotate to next pool.
```

## Reading the columns

| Column | Meaning |
| --- | --- |
| `SYM` | Token symbol. Verify the contract address before acting because symbols are not unique. |
| `V/L` | Rolling one-hour volume divided by current liquidity. A higher number means faster turnover relative to the available liquidity. |
| `S1H` | Total swaps during the rolling one-hour window. This remains the quality baseline and filter. |
| `S5M` | Total swaps during the latest five minutes. This shows what is happening now. |
| `S×` | Swap acceleration: `(S5M × 12) / S1H`. `1.0` means the current pace matches the one-hour baseline, `1.3` or higher is accelerating, and `2.0` or higher is explosive. |
| `MC` | Current token market cap. |
| `FLOW` | Five-minute volume run rate versus rolling one-hour volume, followed by the current direction. |

## FLOW symbols

The first symbol shows volume speed:

```text
🔥  hot       above 1.2
🟢  active    0.8 to 1.2
🟡  cooling   0.5 to 0.8
🧊  cold      below 0.5
```

The second symbol shows direction:

```text
📈  price is rising and buy volume is dominant
📉  price is falling and sell volume is dominant
🔄  mixed, flat, or price and volume do not agree
```

The number after the symbols is the FLOW ratio. For example, `🔥📈1.6` means five-minute volume is running at 1.6 times the one-hour baseline and the short-term direction is bullish.

## Reading S× and FLOW together

`S×` counts transaction acceleration. `FLOW` measures the amount of money moving and its direction. Use both:

```text
S× 1.6 + 🔥📈1.5   swaps and volume are accelerating bullishly
S× 2.1 + 🔥📉2.4   heavy activity, but likely a sell-off rather than a buy signal
S× 1.4 + 🧊🔄0.3   many small swaps without meaningful volume
S× 0.5 + 🧊📈0.4   activity is slowing even if price is briefly rising
```

A high `S×` is not automatically bullish. Bot churn and panic selling can also create a large number of swaps.

## High-momentum example

The radar can also be used to find short, high-momentum bursts. The screenshot below shows BUDDY appearing in the 10:01 AM report with:

```text
V/L      14.2
S1H     9,424
S5M       935
S×        1.2
MC       $152k
FLOW     bullish 1.5
```

By about 10:13 AM, the chart showed market cap near `$306.35k`. That is roughly a `2.02x` move in 12 minutes from the radar snapshot.

![BUDDY high-momentum example](assets/buddy-momentum-example.jpg)

This is the fast-rotation use case:

```text
find accelerating activity
confirm direction with FLOW
manage the position quickly
get out and rotate to the next pool
```

The screenshot is an example, not a performance guarantee. Market cap doubling does not guarantee that every position receives the same return. Entry timing, exit timing, liquidity, slippage, and fees all affect the result. The radar surfaces activity; it does not place trades or decide exits.

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
- FLOW is a five-minute signal against a one-hour baseline. The report runs every five minutes.
- Token symbols are display-only. Use the token address before acting on a result.
- Maximum hold is an operating rule for this setup, not a guarantee of profit.
