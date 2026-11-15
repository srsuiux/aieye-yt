# Files and folders

Everything personal lives in `data/` and `.env`, which are git-ignored. You can back them up or delete them safely.

| Path | What it holds |
|---|---|
| `.env` | Your API keys |
| `data/settings.json` | Your saved default settings |
| `data/config.json` | Advanced settings you changed (models, scenes, look). Only changed values are stored. |
| `data/channel.json` | Your channel's name, description, tags and topic taste |
| `data/credentials/client_secrets.json` | The YouTube client file |
| `data/credentials/youtube_token.pickle` | Your YouTube sign-in |
| `data/db/draft.json` | The topic queue |
| `data/db/final.json` | One short line per finished video |
| `data/ui.json` | Small interface memory, such as whether you finished the welcome tour |
| `data/jobs/<time>/` | One folder per web run: its settings, live events, review answers and result. The 20 most recent are kept. |
| `data/output/<time>/` | Videos being made, or finished but not uploaded |
| `data/experiments/` | Results of the video experiments |

## Code

| Path | What it is |
|---|---|
| `aieye/` | The pipeline, one file per step |
| `aieye/web/` | The web app: server, pages (`templates/`), styles and scripts (`static/`) |
| `docs/` | This documentation, as Markdown. `docs/nav.json` sets the order. |
| `aieye-cli.py` | Entry point for `python3 aieye-cli.py` |
| `start-script.sh` | The `aieye` command |
| `channel.example.json` | A template for `data/channel.json` |

To keep your data somewhere else (for example to try a clean install without touching yours), set `AIEYE_DATA_DIR` to a folder
and `AIEYE_ENV_FILE` to a `.env` path before starting AI Eye.

!!! note
    Never share or commit `.env` or `data/credentials/`. If a key is exposed, delete it in the provider's dashboard and make a new one.
