#!/bin/bash
# AI Eye launcher. Symlinked as `aieye` onto your PATH. Run `aieye help` for usage.
SRC="${BASH_SOURCE[0]}"
while [ -L "$SRC" ]; do                       # follow the symlink back to the real file
  DIR="$(cd "$(dirname "$SRC")" && pwd)"
  SRC="$(readlink "$SRC")"
  [[ "$SRC" != /* ]] && SRC="$DIR/$SRC"
done
ROOT="$(cd "$(dirname "$SRC")" && pwd)"
cd "$ROOT" || exit 1

PY="${AIEYE_PYTHON:-}"
[ -z "$PY" ] && [ -x /opt/anaconda3/bin/python3 ] && PY=/opt/anaconda3/bin/python3
[ -z "$PY" ] && PY="$(command -v python3)"

usage() {
cat <<'EOF'

  AI Eye — YouTube Shorts pipeline

  USAGE
    aieye                         interactive menu
    aieye run [options]           make video(s)
    aieye setup                   choose and save your default settings
    aieye trends                  list what is trending on the web right now (free)
    aieye help                    this page

  RUN OPTIONS  (any order)
    -N                  how many videos: -1, -3, -5 ...
    -def                use saved defaults, ask nothing, random narrator per video
    -trending           topic from what is trending on the web (queue/history not used);
                        with -N each video gets a different trend
    -custom <topic>     your own topic: used as a reference and rewritten to be more
                        engaging (single video). Quotes optional; flags may come before it
    -privacy <p>        public | private | unlisted | none   (none = render only, no upload)
    -quality <q>        low | medium | high                  (image quality, this run only)
    -y                  skip the start countdown

  EXAMPLES
    aieye run -trending -1 -def
    aieye run -custom -1 -def "the ISS, how it floats in space"
    aieye run -5 -def                          5 videos from the topic queue
    aieye run -trending -3 -def -privacy private
    aieye run -1 -def -quality low -privacy none     cheap test, nothing uploaded

  NOTES
    * Posted videos are deleted from data/output/ after a successful upload.
    * Saved defaults live in data/settings.json (change with `aieye setup`).
    * Ctrl+C or q cancels any menu.

EOF
}

cmd="${1:-}"
case "$cmd" in
  run)    shift; exec "$PY" -m aieye run "$@" ;;
  setup)  exec "$PY" -m aieye --setup ;;
  trends) exec "$PY" -c "from aieye.trending import fetch_trends as f; [print(f'{t[\"source\"]:<22} {t[\"title\"]}') for t in f()]" ;;
  help|-h|--help) usage ;;
  "")     exec "$PY" -m aieye ;;
  *)      exec "$PY" -m aieye "$@" ;;
esac
