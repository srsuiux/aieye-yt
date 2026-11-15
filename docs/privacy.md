# Privacy

AI Eye is software you run on your own computer. There is no AI Eye server, no account, no tracking and no analytics. The
authors of AI Eye never receive your keys, topics, videos or channel details.

## What stays on your computer

Everything lives in the folder where you installed AI Eye, mostly under `data/` (see [Files and folders](/docs/files)):

- your API keys, in the `.env` file
- your YouTube sign-in, in `data/` (a token for your own channel)
- your settings, channel details, topic queue and history
- the videos, pictures and audio AI Eye makes

These files are git-ignored so they are not committed by accident. Nobody else can read them unless you share them. If you share
your computer, anyone who can open this folder can read them too.

## What is sent to other companies

AI Eye talks to outside services only when you use a feature that needs them. Each service has its own privacy policy.

| Service | When | What is sent |
|---|---|---|
| **OpenAI** | Writing scripts and topics, narration, pictures, Studio Stills, Script and Film | Your topic, the script text and picture descriptions, and your OpenAI key |
| **OpenRouter** and the video model's company | Studio Clip and Film | Your motion or scene descriptions, the start picture for Clip, and your OpenRouter key |
| **Google / YouTube** | Connecting YouTube and uploading | Your video, title, description, tags and your sign-in. Uploads go to your own channel using your own Google project. |
| **Google Trends** and **Wikimedia** | Only if you choose trending topics | A plain request for today's public trending lists. Nothing about you is sent. |
| **YouTube image servers** (`i.ytimg.com`) | When Home or Library shows a thumbnail | Your browser asks for the public thumbnail of a video you published, and the request does not tell them which page you came from. |
| **PyTorch model download** | First time accurate caption timing runs | A download of a public model file. Nothing about you is sent. |

AI Eye has no way to see what these companies do with your data. Read their policies, and check the settings on your OpenAI
account about data use if that matters to you.

## The web app

`aieye web` listens only on your own computer by default (`localhost`) and refuses requests from other websites. If you choose to
make it reachable from your network, use the access token it prints and only on networks you trust. Anyone who can open the app
can use your keys to spend money and upload to your channel.

## Your choices

- Delete a video from the Library, or delete `data/` to remove everything AI Eye stored.
- Remove a key on the Connections page, or edit `.env`.
- Disconnect YouTube on the Connections page, and remove the app's access in your Google account's security settings.

## Children

AI Eye makes general-audience facts videos. It marks uploads as not made for kids by default. You are responsible for choosing
the right audience setting on your channel.

## Changes

This page describes the software as shipped. If you change the code, you are responsible for what your version does.
