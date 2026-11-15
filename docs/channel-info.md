# Find your channel details

AI Eye adds your channel's name, description and tags to every upload. They live in one file, `data/channel.json`, which is
git-ignored so it never leaves your computer.

## What to put in it

| Field | What it is | Example |
|---|---|---|
| `handle` | Your @handle | `@YourChannel` |
| `url` | Your channel address | `https://www.youtube.com/channel/UC...` |
| `tags` | Tags added to every video | `["Shorts", "Facts", "Science"]` |
| `description` | The text under each video. `{scene_facts}` is replaced by the facts from that video. | see below |
| `audience_notes` | Optional. Who the videos are for and what has worked for you. Used when choosing topics. | text |
| `top_categories` | Optional. The categories that `aieye run -top` rotates through. | list of text |

## Where to find each value on YouTube

1. Open [YouTube Studio](https://studio.youtube.com).
2. **Handle**: **Customization**, then **Basic info**. It is shown under "Handle".
3. **Channel ID and URL**: **Settings**, then **Channel**, then **Advanced settings**. The ID starts with `UC`. Your channel address
   is `https://www.youtube.com/channel/` followed by the ID.
4. **Description**: write it yourself. Keep a line such as "New Short every day" and put `{scene_facts}` where the video's facts
   should go.

## Create the file

```bash
cp channel.example.json data/channel.json
```

Then edit it:

```json
{
  "handle": "@YourChannel",
  "url": "https://www.youtube.com/channel/YOUR_CHANNEL_ID",
  "tags": ["Shorts", "Facts", "Science", "Learning"],
  "description": "Your tagline.\n\nFollow @YourChannel for new Shorts.\n{scene_facts}\n\n#Shorts #Facts #Science"
}
```

Without this file, AI Eye uses a generic description and tags, and still works.

## Check how your videos perform

The topic prompts can use what you learn from YouTube Studio. Open **Analytics**, note which kinds of videos got the most views,
and write that into `audience_notes` as patterns (not specific subjects, or the topic writer will copy them).

!!! note
    Editing these details from a page in the web app arrives in a later update. For now, edit the file.
