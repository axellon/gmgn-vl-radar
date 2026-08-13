# GMGN V/L Radar

A small Solana pool scanner built around GMGN market data. It ranks active pools by hourly volume relative to liquidity, adds a short-term flow reading, and posts the result to Telegram.

The same report also shows the first DLMM row from Meteora's **Discover > New Tokens** page, including market cap, volume, TVL, fees, token age, and pool age.

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

## Output

```text
GMGN V/L — 20:01 Bali

SOLANA
SYM       VOL   LIQ  V/L  SWP    MC   FLOW
------------------------------------------
App      573k   78k  7.3 5657  815k  🧊🔄0.5

K-HOME   619k  337k  1.8 4964  1.5M  🔥📉2.4

BOIÚNA   105k   84k  1.3 1674  704k  🔥📈1.6

METEORA NEW #1
PAIR         MC   VOL   TVL   FEE
---------------------------------
CGOD-SOL    31k     0     0     0
AGE token 18m | pool 18m

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
- `METEORA NEW #1` mirrors the current first row under Meteora Discover > New Tokens with the DLMM filter selected.
- FLOW is a five-minute signal against a one-hour baseline. The report runs every five minutes.
- Token symbols are display-only. Use the token address before acting on a result.
- Maximum hold is an operating rule for this setup, not a guarantee of profit.
