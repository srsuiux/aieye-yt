# Get an OpenAI key

AI Eye uses OpenAI to write the script, speak it and draw the pictures. You pay OpenAI directly for what you use.

## Steps

1. Create an account at [platform.openai.com](https://platform.openai.com).
2. Add credits: open **Billing** and add a small amount. $5 pays for several videos. New credits can take a few minutes to appear.
3. Open **API keys** and choose **Create new secret key**. Give it a name such as "AI Eye".
4. Copy the key. It starts with `sk-` and is shown **once**.
5. In AI Eye, open [Connections](/connections), paste it under **OpenAI** and press **Save key**, then **Test**.

!!! warning
    Treat the key like a password. Do not post it, commit it or put it in a screenshot. If it leaks, delete it in the OpenAI
    dashboard and create a new one.

## Without the web app

Create a file called `.env` in the AI Eye folder with one line:

```
OPENAI_API_KEY=sk-your-key-here
```

## Check your spending

AI Eye prints the cost of each video. For your account total, use the usage page in the OpenAI dashboard. You can also set a
monthly limit there.

## If it does not work

| Message | Meaning |
|---|---|
| Test says the key was rejected | The key was copied wrongly, or deleted. Create a new one. |
| `insufficient_quota` while making a video | No credits left. Add credits in Billing. |
| Rate limit messages | Normal for pictures. AI Eye waits and retries by itself. |
