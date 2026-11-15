# Get an OpenRouter key

OpenRouter is only needed for the [video experiments](/docs/experiments) (AI video clips). Regular videos do not use it.

## Steps

1. Create an account at [openrouter.ai](https://openrouter.ai).
2. Add credits at [openrouter.ai/credits](https://openrouter.ai/credits).
3. Open [openrouter.ai/keys](https://openrouter.ai/keys) and create a key. It starts with `sk-or-`.
4. In AI Eye, open [Connections](/connections), paste it under **OpenRouter** and press **Save key**, then **Test**.

!!! warning
    None of the AI video models are free. Every experiment shows a price first. Read [Costs and limits](/docs/costs) before you
    start one.

## Without the web app

Add this line to `.env` in the AI Eye folder:

```
OPENROUTER_API_KEY=sk-or-your-key-here
```

## See model prices

```bash
aieye models
```

Lists the video models with their live prices. It is free.
