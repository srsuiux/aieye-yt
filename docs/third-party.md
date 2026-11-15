# Third-party software and services

AI Eye is built on other people's work. It does not include their code in this repository; `pip install -r requirements.txt`
downloads it, and each package keeps its own license. Check a package's page for its exact terms.

| Package | Used for |
|---|---|
| openai | Talking to OpenAI for scripts, voice and pictures |
| requests | Web requests, such as OpenRouter and trending lists |
| FastAPI, uvicorn, Jinja2, markdown | The web app and these docs |
| Pillow, NumPy | Drawing pictures and captions |
| MoviePy, imageio-ffmpeg, ffmpeg | Building the video. ffmpeg is a separate program with its own license terms. |
| google-api-python-client, google-auth-oauthlib | YouTube upload and sign-in |
| PyTorch, torchaudio | Optional accurate caption timing |
| pyobjc (macOS only) | Text shaping for non-Latin captions |

## Services

AI Eye connects to OpenAI, OpenRouter (and the video models behind it), Google and YouTube, Google Trends and Wikimedia. Their
terms apply to your use of them. See [Privacy](/docs/privacy) for what is sent, and [Terms of use](/docs/terms).
