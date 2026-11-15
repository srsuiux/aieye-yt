# Security

AI Eye runs on your own computer and holds your API keys and YouTube sign-in, so please report problems privately.

## Reporting a problem

Use GitHub's **Report a vulnerability** option on the repository's Security tab (private security advisory). Please do not open a
public issue for a security problem, and never post keys, tokens or the contents of your `.env` or `data/` folder anywhere.

Include what you found, the steps to reproduce it, and your version or commit. This is a volunteer project, so replies may take a
few days.

## What is in scope

- The web app (`aieye web`): the local-only guard, token access, file serving, and anything that lets another website or another
  computer use someone's keys or channel.
- Handling of keys and the YouTube token.

## If you leaked a key

Delete it at the provider right away (OpenAI, OpenRouter, Google Cloud) and make a new one. Removing it from git history is not
enough.
