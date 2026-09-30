#!/bin/bash
# Double-click: make 1 video with your saved defaults and upload it
cd "$(dirname "$0")" || exit 1
PY=/opt/anaconda3/bin/python3
[ -x "$PY" ] || PY=$(command -v python3)
"$PY" ysa-cli.py --quick
echo
read -n 1 -s -r -p "Finished. Press any key to close this window."
