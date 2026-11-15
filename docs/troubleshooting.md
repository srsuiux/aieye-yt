# Troubleshooting

| Problem | Fix |
|---|---|
| The browser does not open | Open `http://localhost:8420` yourself. Use `aieye web --port 9000` if the port is taken. |
| "Unknown host" or a blank page | Open the app with `localhost` or `127.0.0.1`, not a different name. |
| Test says the key was rejected | Copy the key again from the provider's dashboard. |
| `insufficient_quota` / no credits | Add credits at platform.openai.com under Billing. New credits can take a few minutes. |
| Rate limit messages | Normal. AI Eye waits and retries. If it keeps happening, lower `IMAGE_WORKERS` in `aieye/config.py`. |
| `OPENAI_API_KEY not set` | Save the key on the [Connections page](/connections) or in `.env`. |
| `No saved defaults yet` | Run `aieye setup` once. |
| `ffprobe: command not found` | Install ffmpeg: `brew install ffmpeg`. |
| Captions use "estimated timing" | Run `pip install torch torchaudio`. Captions still work, just less precisely. |
| YouTube sign-in stops working after a week | Normal while your Google app is in Testing. Press **Sign in with Google** again. |
| Upload fails | The video is still saved in `data/output/`. Check the client file, then sign out and in again on the Connections page. |
| Uploads stay private | Google restricts new unaudited API projects. See [Set up YouTube uploads](/docs/youtube-setup). |
| The Create button is disabled | A run is in progress, or the OpenAI key is missing. Open the run, or add the key on Connections. |
| A run says "stopped unexpectedly" | The process was closed (for example the computer slept or the app was stopped). Open Details for the output, then start again. |
| A cancelled run left a topic "being made" | Open [Topics](/topics) and press Return to queue. |
| The review video does not play | The file may still be finishing. Wait a few seconds and reload the run page. |
| "I can't create more than N videos a day" | The daily safety limit (3 by default). Try again tomorrow, or raise it under Settings, Advanced, Limits. |
| A video in a batch failed | The others carry on. The summary lists each result. |
