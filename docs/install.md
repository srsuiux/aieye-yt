# Install and first run

## 1. Get the code

```bash
git clone https://github.com/srsuiux/aieye-yt.git
cd aieye-yt
```

## 2. Install the requirements

```bash
pip install -r requirements.txt
brew install ffmpeg        # Mac. On Linux: sudo apt install ffmpeg
```

The first video downloads a caption-timing model of about 1.2 GB. It happens once.

## 3. Start the web app

```bash
python3 aieye-cli.py web
```

A browser tab opens at `http://localhost:8420`. If it does not, open that address yourself.

!!! note
    To type just `aieye` instead of `python3 aieye-cli.py`, run this once from the AI Eye folder:
    `ln -sf "$PWD/start-script.sh" ~/.local/bin/aieye`. Then `aieye web` works from anywhere.

## 4. Add your key

Open **Connections**, paste your OpenAI key, press **Save key**, then **Test**. See [Get an OpenAI key](/docs/get-openai-key) if you
do not have one yet.

## 5. Make your first video

Until the Create page ships in the web app, make videos from the terminal:

```bash
aieye run -1 -def
```

This asks nothing, shows the settings and an estimated cost, and starts after a short countdown. Press Ctrl+C to cancel.

!!! warning
    If upload privacy is `public`, the finished video is published at once. Choose `private` or `none` (render only) in your
    [settings](/docs/settings) until you trust the output.

## Stop the web app

Press Ctrl+C in the terminal where you started it.
