# Terminal commands

Everything the web app can do can also be done from the terminal. Run `aieye help` for the short version.

## Commands

| Command | What it does |
|---|---|
| `aieye` | Interactive menu |
| `aieye web` | Start the [web app](/docs/web-app) (`aieye -web` also works) |
| `aieye run [options]` | Make videos |
| `aieye setup` | Choose and save your default settings |
| `aieye trends` | List what is trending on the web right now (free) |
| `aieye models` | List video models and live prices (free) |
| `aieye menu` | The AI video studio (spends OpenRouter credit) |
| `aieye help` | Show help |

## Options for `aieye run`

| Option | Meaning |
|---|---|
| `-1` or `-3` | Make 1 or 3 videos. Nothing else is allowed, and never more than 3 a day. |
| `-def` | Use your saved defaults and ask nothing. A random narrator is used. |
| `-trending` | Topic comes from what is trending on the web |
| `-top` | Topics from the top categories, with photo-real close-ups |
| `-custom your topic` | Your own topic (one video). Quotes are optional. |
| `-en -hindi ...` | One video per language from the same topic: `-en -hi -es -fr -de -pt -it -id -tr` |
| `-privacy P` | `public`, `private`, `unlisted` or `none` for this run |
| `-quality Q` | `low`, `medium` or `high` for this run |
| `-y` | Skip the start countdown |

## Examples

```bash
aieye run -1 -def                                  # one video from the queue
aieye run -trending -1 -def -privacy private       # one trending topic, uploaded as private
aieye run -3 -def -quality low -privacy none       # cheap test, nothing uploaded
aieye run -custom -1 -def -en -hindi "why we yawn" # English and Hindi from one topic
```

## Without the `aieye` command

Use `python3 aieye-cli.py` instead of `aieye` in every example, for instance `python3 aieye-cli.py web`.
