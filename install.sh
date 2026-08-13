#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.hermes/scripts" "$HOME/gmgn-volume-monitor" "$HOME/.config/gmgn-dlmm-radar"
install -m 0755 "$ROOT/gmgn-dlmm-radar.py" "$HOME/.hermes/scripts/gmgn-dlmm-radar.py"
install -m 0644 "$ROOT/filter_query.json" "$HOME/gmgn-volume-monitor/filter_query.json"

if [[ ! -f "$HOME/.config/gmgn-dlmm-radar/telegram.env" ]]; then
  install -m 0600 "$ROOT/telegram.env.example" "$HOME/.config/gmgn-dlmm-radar/telegram.env"
  printf '%s\n' "Created ~/.config/gmgn-dlmm-radar/telegram.env — fill in Telegram credentials."
fi

printf '%s\n' "Files restored. Configure GMGN CLI and recreate the Hermes cron from cron-manifest.json."
