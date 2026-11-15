# Settings

Open **Settings** from the left menu, or go to `/settings`. You can also choose defaults in the terminal with `aieye setup`. Both
read and write the same file, `data/settings.json`.

## Defaults for new videos

Change a value and press **Save defaults**.

| Setting | Options |
|---|---|
| Image style | `representational` (labelled diagrams, best for facts), `realistic` (photographic), `illustrated` |
| Image quality | `low` (about $0.005 a picture), `medium` (about $0.010), `high` (about $0.041) |
| Upload privacy | `public`, `private`, `unlisted`, `none` (render only, do not upload) |
| Narrator voice | `marin`, `cedar`, `nova`, `coral`, `sage`, `ash`, `ballad`, `verse`, `alloy`, `echo`, `fable`, `onyx`, `shimmer` |
| Voices in a batch | `shuffle` (a different narrator per video) or `same` |

**Review each video before it uploads** (web app) is saved with the defaults and pre-fills the [Create page](/docs/create). It is on
unless you turn it off. The terminal ignores it and uploads straight away.

!!! warning
    With privacy set to `public`, every finished video is published immediately, including all three in a batch. Use `private`
    until you trust the output, or `none` to review the files first.

## Change one run only

```bash
aieye run -1 -def -privacy private -quality low
```

`-privacy` and `-quality` override your saved defaults for that run and change nothing on disk.

## Advanced

The **Advanced** card on the Settings page holds the models and the look of the video. Open a group, change a value, and press
**Save advanced settings**. A changed value shows a "Changed" label and a **Reset** link. **Reset all** puts every value back.
The next video you make uses the new values; a video already running does not.

Only the values you changed are saved, in `data/config.json`. The rest follow the built-in defaults.

| Group | Setting | Range or options |
|---|---|---|
| Limits | Videos pushed to YouTube per day | 1 to 10 (default 3). A safety brake; runs are still 1 or 3 videos. |
| Models | Script model, Voice model, Image model | Any model id your account can use. One word, no spaces. |
| Script and pictures | Scenes per video | 3 to 7 (default 5) |
| | Pictures per scene (most) | 1 to 3 (default 3). 1 is the cheapest. |
| | Shortest picture, in words | 2 to 12 (default 5) |
| | Scenes drawn at once | 1 to 6 (default 3). Lower it if you hit rate limits. |
| | Topics added when the queue is empty | 3 to 20 (default 10) |
| Narration | Narrator direction | Tone and pacing text sent with every line |
| | Voices used when shuffling | At least two of the 13 voices |
| | Reading level and tone rules | Rules every script follows. Change them if your audience is not 8 to 12. |
| Look | Zoom strength | low, medium, high |
| | Crossfade length | 0 to 0.6 seconds (default 0.28) |
| | Caption highlight | plate or text |
| | Caption colours | shuffle or fixed |
| | Caption accent colour | A colour, used when colours are fixed |
| | Words per caption | 2 to 8 (default 5) |
| | Scenes rendered at once | 1 to 6 (default 3). Higher is faster but uses more memory. |

!!! warning
    Changing scenes per video or pictures per scene changes the cost of every video. The cost shown next to image quality assumes
    the default values.

If you edit `data/config.json` by hand, any value that is out of range is ignored and the default is used, so a typing mistake
cannot stop a run.

Your channel's name, description and tags are on the [Channel page](/docs/channel-info).
