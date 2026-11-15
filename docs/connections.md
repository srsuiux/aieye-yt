# The Connections page

Open it from the left menu or at `/connections`. It holds everything AI Eye needs to talk to other services.

## API keys

Each key has a card with three states:

- **Not set**: nothing saved yet.
- **Saved …abcd**: a key is saved; the last 4 characters are shown so you can recognise it.

| Button | What it does |
|---|---|
| Save key | Writes the key to `.env` in the AI Eye folder and uses it straight away. No restart needed. |
| Test | Sends a free request to check the service accepts the key. It does not spend credits. |
| Remove | Deletes the key from `.env`. |

Pasting a new key over an existing one replaces it.

| Key | Used for | Required |
|---|---|---|
| OpenAI (`OPENAI_API_KEY`) | Script, voice and pictures | Yes |
| OpenRouter (`OPENROUTER_API_KEY`) | The [video experiments](/docs/experiments) | No |

## YouTube

Uploading needs two things, in this order:

1. **The client file.** A small JSON file from Google Cloud. Choose it and press **Save client file**. AI Eye checks that it is a
   *Desktop app* client and saves it to `data/credentials/client_secrets.json`. [How to create it](/docs/youtube-setup).
2. **Sign in.** Press **Sign in with Google**. A Google page opens on this computer. Choose your channel's account and allow
   uploads. When it finishes, the card says **Signed in**.

**Sign out** deletes the saved sign-in but keeps the client file. Saving a new client file also signs you out, because the old
sign-in belongs to the old client.

!!! note
    Without YouTube you can still make videos. Set upload privacy to `none` in your [settings](/docs/settings) and the finished
    video is saved on your computer.

## Where things are saved

| What | Where |
|---|---|
| API keys | `.env` in the AI Eye folder |
| YouTube client file | `data/credentials/client_secrets.json` |
| YouTube sign-in | `data/credentials/youtube_token.pickle` |

All of these are git-ignored, so they are never committed.
