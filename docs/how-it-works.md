# How a video is made

A video is about 45 to 55 seconds, vertical (1080 by 1920), with 10 to 12 pictures and word-highlighted captions.

| Step | What happens |
|---|---|
| 0. Topic | Takes the next topic from the queue or asks the model for fresh ones for kids aged 8 to 12. A strict check rejects any topic about the same animal, object or phenomenon as an earlier video. A custom or trending topic can replace this. |
| 1. Script | Research (fact-checked), then a draft written to be spoken, then a read-aloud edit that removes stiff phrases. Each of the 5 scenes is split into 2 or 3 shots. |
| 2. Voice | One narration request per scene, with a delivery note. Silence is trimmed. |
| 3. Pictures | One image per shot. The first shot of a scene is fresh; the others are edited from it so the subject and look stay the same. |
| 4. Video | Captions are timed to the real audio. Each picture gets a slow zoom and a short crossfade. Loudness is set to -14 LUFS, YouTube's target. |
| 5. Upload | Title, description and tags go to YouTube. Privacy comes from your settings. |

## Review before uploading

When you create a video in the web app, you can choose to review it before it uploads. The app then pauses after the video is
made, shows a preview, and lets you edit the title, description, tags and privacy before you upload or skip. The choice is
pre-filled from your saved default. (The Create page arrives in a later update.)

## After a run

- **Uploaded:** the whole run folder is deleted. Only a short line stays in `data/db/final.json`.
- **Not uploaded or upload failed:** `short.mp4` and `youtube_metadata.json` are kept in `data/output/<time>/`.
