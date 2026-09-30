#!/bin/bash
# Double-click: choose and save your default settings
cd "$(dirname "$0")" || exit 1
PY=/opt/anaconda3/bin/python3
[ -x "$PY" ] || PY=$(command -v python3)
"$PY" ysa-cli.py --setup
echo
read -n 1 -s -r -p "Finished. Press any key to close this window."
