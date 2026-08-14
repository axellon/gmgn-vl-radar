#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_DIR="$HOME/.hermes/scripts"
CONFIG_DIR="$HOME/.config/gmgn-dlmm-radar"
FILTER_DIR="$HOME/gmgn-volume-monitor"

mkdir -p "$SCRIPT_DIR" "$CONFIG_DIR" "$FILTER_DIR"
install -m 0755 "$ROOT/src/gmgn-dlmm-radar.py" "$SCRIPT_DIR/gmgn-dlmm-radar.py"
install -m 0644 "$ROOT/config/filter-query.json" "$FILTER_DIR/filter_query.json"
install -m 0644 "$ROOT/config/robinhood-filter-query.json" "$FILTER_DIR/robinhood_filter_query.json"

if [[ ! -f "$CONFIG_DIR/telegram.env" ]]; then
  install -m 0600 "$ROOT/telegram.env.example" "$CONFIG_DIR/telegram.env"
  printf '%s\n' "Created $CONFIG_DIR/telegram.env"
fi

printf '%s\n' "Installed $SCRIPT_DIR/gmgn-dlmm-radar.py"
printf '%s\n' "Edit $CONFIG_DIR/telegram.env, configure GMGN CLI, then add the job from config/cron.json."
