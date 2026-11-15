# Costs and limits

You pay OpenAI (and OpenRouter, for experiments) directly. AI Eye shows an estimate before it starts and the real cost after.

## Typical cost of one video

| Image quality | One video | Three videos |
|---|---|---|
| low | about $0.16 | about $0.48 |
| medium | about $0.21 | about $0.64 |
| high | about $0.56 | about $1.67 |

Pictures are most of the cost. A fresh picture costs about $0.005, $0.010 or $0.041 (low, medium, high). A second or third shot in a
scene is edited from the first and costs the same plus about $0.014. Each extra language costs about $0.02.

Narration cost is an estimate, because the API does not report it.

## Limits that protect you

- **3 videos a day.** AI Eye counts videos pushed to YouTube today and refuses a run that would go over. A video that was only
  rendered, or whose upload failed, does not count.
- **1 or 3 videos per run.** No other batch size.
- **Confirm before spending.** The terminal shows the settings and cost, then waits a few seconds (Ctrl+C cancels). The web app shows the cost and asks you to press **Start and spend**.
- **Experiments show a price first.** See [Video experiments](/docs/experiments).

## Keep the bill low

- Test with `-quality low -privacy none`.
- Use `medium` for real videos. `high` costs about three times as much for a small gain.
- Set a monthly limit in your OpenAI dashboard.
