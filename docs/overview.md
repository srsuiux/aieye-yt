# What AI Eye does

AI Eye turns a topic into a finished YouTube Short: a written script, a narrator's voice, AI pictures, a slowly moving
video with word-by-word captions, and, if you want, the upload to your channel.

It is a tool you run yourself, on your own computer, with your own accounts. Nothing is sent to an AI Eye server,
because there is none. Your keys, your channel details and your videos stay in the AI Eye folder.

## Ways to use it

| | Terminal | Web app | Assistant (beta) |
|---|---|---|---|
| Start | `aieye run ...` | `aieye web` | `aieye web`, then the Assistant page |
| Best for | Fast, repeatable runs and scripts | Setting everything up, managing topics, changing settings | Describing a video in plain words and watching it get made |
| Same pipeline | Yes | Yes | Yes |
| Same settings and files | Yes | Yes | Yes |

You can switch between them at any time. A video started in one shows up in the others. The web app also has **Studio** (beta), for
experiments with AI video. See [The web app](/docs/web-app) and [Assistant](/docs/assistant).

## What you need

- Python 3.10 or newer
- An OpenAI account with credits ([get a key](/docs/get-openai-key))
- ffmpeg installed (`brew install ffmpeg` on a Mac)
- Optional: a Google account for uploads ([set up YouTube](/docs/youtube-setup))
- Optional: an OpenRouter account for the video experiments (Studio and the terminal experiments) ([get a key](/docs/get-openrouter-key))

## What a video costs

About $0.16 to $0.56 per video, depending on picture quality. Read [Costs and limits](/docs/costs) before your first run.

!!! note
    AI Eye refuses to push more than 3 videos to YouTube in one day. This is a safety limit, not a bug.

## Next step

[Install and first run](/docs/install)
