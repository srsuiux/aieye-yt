# The web app

Start it with `aieye web`. It runs on your computer and opens in your browser.

## Pages

Every part of the app has its own address, so you can bookmark it and use the back button.

| Page | Address | What it is for |
|---|---|---|
| Home | `/` | Today's upload count out of 3, a setup checklist and your recent videos |
| Create | `/create` | Make 1 or 3 videos: topic, languages, look, cost estimate, confirm. See [Create a video](/docs/create) |
| Run | `/runs/<id>` | Watch a run live, review the finished video, cancel |
| Library | `/library` | Videos not uploaded yet (preview, edit, upload, delete), uploaded videos, recent runs. See [Library](/docs/library) |
| Topics | `/topics` | The queue of topics: add, reorder, remove, and see what is already made. See [Topics](/docs/topics) |
| Channel | `/channel` | Your handle, description, tags and topic taste. See [Channel details](/docs/channel-info) |
| Settings | `/settings` | Defaults for new videos (style, quality, privacy, narrator) and the advanced models and look. See [Settings](/docs/settings) |
| Connections | `/connections` | Save your OpenAI and OpenRouter keys, add the YouTube client file, sign in to YouTube |
| Docs | `/docs` | This documentation |

The video experiments (Studio) arrive in a later update. This page lists only what exists today.

## Addresses

Pages live under your channel handle, the same way YouTube does it: `http://localhost:8420/@YourHandle/create`,
`/@YourHandle/library`, and so on. Set your handle on the **Channel** page. Until you do, pages live under `/new`, for example
`http://localhost:8420/new/create`. Saving a handle moves you to the new address, and old or unprefixed addresses redirect to the
right one, so bookmarks keep working.

## Your first visit and the tour

On a brand-new install (no OpenAI key, no saved settings, nothing made yet) the Home page opens with a **Welcome** card and a
short tour. The tour is nine steps: what AI Eye does, then Connections, Settings, Channel, Topics, Create, Library and Docs, one at
a time, with the page's menu item highlighted. A last step points you to adding your OpenAI key.

| Key or button | What it does |
|---|---|
| **Next** or the right arrow | Next step |
| **Back** or the left arrow | Previous step |
| **Skip tour** or Esc | Close the tour. It will not open on its own again. |
| **?** in the top bar | Open the tour again at any time |

Finishing or skipping is remembered in `data/ui.json`. People who already have a key or saved settings never see it open by itself.

An empty install is safe to explore: every page opens, and pages that have nothing to show say what to do next. Create stays
disabled until you add your OpenAI key.

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
- Each video is made in its own process, so Cancel stops it cleanly and your latest settings always apply.
- Keys are never sent back to the browser. You see only the last 4 characters.
- Keys are written to `.env` in the AI Eye folder with owner-only permissions.

## Theme

The moon button in the top bar switches between light and dark. By default the app follows your system setting.

## Notices in the app

The key points of [Privacy](/docs/privacy), [Terms of use](/docs/terms) and [Copyright and content](/docs/copyright) are shown
where they matter: on Connections (where each key is sent, keep it secret, YouTube terms), on Create and Studio (this spends real
money; what is sent to which company), before upload in the review step and the Library (check the facts, label AI content), in
the welcome card and tour, and in the footer of every page.
