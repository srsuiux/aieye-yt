#!/bin/bash
# Double-click: make 5 videos back to back with your saved defaults and upload them
cd "$(dirname "$0")" || exit 1
PY=/opt/anaconda3/bin/python3
[ -x "$PY" ] || PY=$(command -v python3)
"$PY" ysa-cli.py --batch 5
echo
read -n 1 -s -r -p "Finished. Press any key to close this window."
