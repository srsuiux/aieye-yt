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
    aieye                         menu: new video, script only, make video, rebuild final, upload, status
    aieye web [--port N]          open the web app in your browser (local only; --host to share, --no-open)
    aieye run [options]           make video(s)
    aieye setup                   choose and save your default settings
    aieye trends                  list what is trending on the web right now (free)
    aieye models                  list image-to-video models and their live prices (free)
    aieye help                    this page

  RUN OPTIONS  (any order)
    -1 / -3             how many videos: 1 or 3 only (daily cap: 3 pushed to YouTube; change in the web app Settings)
    -def                use saved defaults, ask nothing, random narrator per video
    -trending           topic from what is trending on the web (queue/history not used);
                        with -3 each video gets a different trend
    -custom <topic>     your own topic: used as a reference and rewritten to be more
                        engaging (single video). Quotes optional; flags may come before it
    -en -hindi ...      languages: one video per language from the SAME topic and pictures
                        (-en -hi -hindi -es -spanish -fr -de -pt -it -id -tr); default is English only
    -img [N] "prompt"   EXPERIMENT: N (1-4) high-definition, centre-focus 9:16 stills for image-to-video tests.
                        Saved in data/experiments/images/. No video, no upload, not counted in the daily limit.
                        Quality defaults to high (-quality low|medium|high to change)
    -vid [still.png] "motion"
                        EXPERIMENT: turn a still into a clip with an image-to-video model via OpenRouter.
                        Default model Veo 3.1 Lite, 720p, 5 s, 9:16. Uses the newest -img still if
                        no file is given. Saves the clip, its last frame (start of the next clip) and the cost in
                        data/experiments/videos/. -model <id>  -dur <1-10>  -res 480p|720p|1080p
                        Needs OPENROUTER_API_KEY in .env. Shows the price first; -y skips the 3 s cancel window.
    -script "topic"     EXPERIMENT: ONLY the script. A reasoning model researches and drafts it, a stronger one judges it
                        against a strict rubric, and it is revised until it passes (max 2 rounds). Costs a few dollars at
                        most, makes no video. -notes <file> gives it verified facts. Saved in data/experiments/film/<run>/
                        (script.json, script.md, script_report.json); make the video later with  -film -resume <run>
                        -script -resume <run> re-judges and improves an existing script (keeps the old one as script_prev.json)
    -film "topic"       EXPERIMENT: the FULL pipeline with text-to-video. A director writes a kid-level, paced shot list
                        (slow motion on the peak action), then voice, one text-to-video clip per scene, word-timed
                        captions, loudness-normalised 9:16 output. Saved in data/experiments/film/<run>/.
                        -model <id>  -res 480p|720p|1080p  -ambient (keep the clips' own sound, quietly)
                        -resume <folder> (finish a run, generating only missing clips)
                        -qa (check every clip with a vision model for spoilers, drawn graphics and wrong
                        content; failing clips are regenerated up to 2 times, so up to 3x clip cost. Off by default)
                        -y (skip the cancel window)
    -privacy <p>        public | private | unlisted | none   (none = render only, no upload)
    -quality <q>        low | medium | high                  (image quality, this run only)
    -y                  skip the start countdown

  EXAMPLES
    aieye run -trending -1 -def
    aieye run -custom -1 -def "the ISS, how it floats in space"
    aieye run -custom -1 -def -en -hindi "the ISS, how it floats"   English + Hindi
    aieye run -3 -def                          3 videos from the topic queue
    aieye run -trending -3 -def -privacy private
    aieye run -img 1 "a red fox in fresh snow"        experiment still, 9:16, high quality
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
  models) exec "$PY" -c "from aieye.videxp import list_models; [print(f'{m[\"id\"]:<42}{m.get(\"pricing_skus\")}') for m in list_models()]" ;;
  trends) exec "$PY" -c "from aieye.trending import fetch_trends as f; [print(f'{t[\"source\"]:<22} {t[\"title\"]}') for t in f()]" ;;
  menu)   exec "$PY" -m aieye menu ;;
  help|-h|--help) usage ;;
  "")     exec "$PY" -m aieye ;;
  *)      exec "$PY" -m aieye "$@" ;;
esac
