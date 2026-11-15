# The web app

Start it with `aieye web`. It runs on your computer and opens in your browser.

## Pages

Every part of the app has its own address, so you can bookmark it and use the back button.

| Page | Address | What it is for |
|---|---|---|
| Home | `/` | Today's upload count out of 3, a setup checklist and your recent videos |
| Connections | `/connections` | Save your OpenAI and OpenRouter keys, add the YouTube client file, sign in to YouTube |
| Docs | `/docs` | This documentation |

More pages arrive in later updates. This page lists only what exists today.

## Options

```bash
aieye web                      # http://localhost:8420, opens your browser
aieye web --port 9000          # use another port
aieye web --no-open            # do not open the browser
aieye -web                     # same as: aieye web
```

## Who can open it

By default the app listens on `127.0.0.1`, so **only this computer** can open it. The page shows a "Local only" badge in the
top bar.

To open it from another device on your network, start it with a host:

```bash
aieye web --host 0.0.0.0
```

The app then prints a link that contains a random access token. The badge changes to "Network access on".

!!! warning
    Anyone with that link can use your API keys, spend your credits and upload to your channel. Only use it on a network you
    trust and never share the link. The token changes every time you start the app.

## Protection built in

- The app refuses requests whose `Host` header is not `localhost` or `127.0.0.1`, which blocks DNS-rebinding attacks.
- Changes (saving a key, signing in) are accepted only from the app's own pages. Other websites cannot trigger them.
- Keys are never sent back to the browser. You see only the last 4 characters.
- Keys are written to `.env` in the AI Eye folder with owner-only permissions.

## Theme

The moon button in the top bar switches between light and dark. By default the app follows your system setting.
