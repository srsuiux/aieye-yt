# Video experiments

These are side tools for trying AI video. They never touch your topic queue or the daily upload limit, and they never upload.
Results go to `data/experiments/`.

!!! warning
    None of the video models are free. Every command shows a price first. `-y` skips the pause, so use it with care.

You need an [OpenRouter key](/docs/get-openrouter-key) for the video commands. `-img` and `-script` only need OpenAI.

| Command | What it does |
|---|---|
| `aieye run -img [N] "prompt"` | 1 to 4 centre-focus 9:16 pictures |
| `aieye run -vid [still.png] "motion"` | Turn a picture into a short clip |
| `aieye run -script "topic"` | Write only the script. Judged and revised before saving. |
| `aieye run -film "topic"` | The whole pipeline with AI video clips |
| `aieye menu` | A guided version: choose a model, see the price, confirm |

## Options

| Option | Applies to | Meaning |
|---|---|---|
| `-model ID` | `-vid`, `-film` | `grok`, `veo`, `veo-fast`, `seedance`, `kling`, or any OpenRouter model id. Default `google/veo-3.1-lite`. |
| `-res R` | `-vid`, `-film` | `480p`, `720p` (default) or `1080p` |
| `-dur S` | `-vid` | Clip length in seconds, 1 to 10 |
| `-ambient` | `-film` | Keep the clips' own sound, quietly |
| `-qa` | `-film` | Check each clip with a vision model and redo bad ones. Can cost up to 3 times the clip price. Off by default. |
| `-resume DIR` | `-film`, `-script` | Continue a saved run |
| `-notes FILE` | `-script` | Give the script verified facts to use |

A sensible order: run `-script` first (cheap) and read the script, then `-film -resume <run>` to spend on video.

!!! note
    The experiments are not in the web app yet. A Studio page is planned.
