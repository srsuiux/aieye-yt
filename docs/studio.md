# Studio (beta)

Studio is a **beta**: an experiment that is tested less than the rest of AI Eye. Tools, models, prices and results can change or
break between versions.

Studio is for trying AI video before you use it in a real video. It never touches your topic queue, your daily upload limit
or YouTube. Everything it makes is saved in `data/experiments/` and shown on the Studio page.

Studio needs an OpenAI key for Stills, Script and Film, and an [OpenRouter key](/docs/get-openrouter-key) for Clip and Film.
Add them on the [Connections](/connections) page.

!!! warning
    None of the video models are free. Every tool shows the cost before it starts and asks you to confirm. Nothing is
    spent until you press **Yes, spend it**.

## The four tools

| Tool | What it makes | Typical cost |
|---|---|---|
| **Stills** | 1 to 4 sharp 9:16 pictures with the subject in the centre | about $0.04 each at high quality |
| **Clip** | One short clip that starts from one of your stills, plus its last frame | set by the model, usually under $1 |
| **Script** | Only the script: it is researched, drafted, judged and revised. No video. | up to a few dollars |
| **Film** | A whole video made with AI video: shot list, voice, a clip for each scene, captions and loudness | the most expensive: about $0.30 plus the model's price for about 30 seconds |

## Using a tool

1. Open **Studio** and choose a tool.
2. Fill in the form. The **Cost** box on the right updates as you change things.
3. Press **Make it**, then **Yes, spend it**.
4. Watch the run. It shows the latest step, the cost so far and a **Cancel run** button. Money already spent stays spent.
5. When it finishes, the pictures, clips or script appear on the page and in **Recent results** on the Studio page.

Only one thing runs at a time, including normal videos from Create.

## Choosing a video model

Clip and Film read the live price list from OpenRouter. **Veo 3.1 Lite** is listed first because it gave the best action and
anatomy for the price in our tests. Some models are priced per token, so their cost shows as unknown until the run finishes.

For Film, **Check each clip** lets a vision model inspect every clip and redo bad ones, up to twice. This gives better results,
and every redo is billed again, so the cost box shows the worst case.

## The same tools in the terminal

See [Terminal commands](/docs/terminal) and [Video experiments](/docs/experiments).
