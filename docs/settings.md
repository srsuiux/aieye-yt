# Settings

Your defaults are saved in `data/settings.json`. Choose them once with `aieye setup` (or `python3 aieye-cli.py --setup`).

| Setting | Options |
|---|---|
| Image style | `representational` (labelled diagrams, best for facts), `realistic` (photographic), `illustrated` |
| Image quality | `low` (about $0.005 a picture), `medium` (about $0.010), `high` (about $0.041) |
| Upload privacy | `public`, `private`, `unlisted`, `none` (render only, do not upload) |
| Narrator voice | `marin`, `cedar`, `nova`, `coral`, `sage`, `ash`, `ballad`, `verse`, `alloy`, `echo`, `fable`, `onyx`, `shimmer` |
| Voices in a batch | `shuffle` (a different narrator per video) or `same` |

!!! warning
    With privacy set to `public`, every finished video is published immediately, including all three in a batch. Use `private`
    until you trust the output, or `none` to review the files first.

## Change one run only

```bash
aieye run -1 -def -privacy private -quality low
```

`-privacy` and `-quality` override your saved defaults for that run and change nothing on disk.

## Advanced

Models, number of scenes, caption look, zoom strength and more are constants in `aieye/config.py`. The README lists each one.
Your channel's name, description and tags are in [`data/channel.json`](/docs/channel-info).
