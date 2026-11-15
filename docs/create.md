# Create a video

Open **Create** from the left menu, or go to `/create`. Every field is filled in from your saved [settings](/docs/settings), so for
a normal video you only press **Make video**. Changes on this page apply to this run only; your saved settings stay as they are.

## The form

| Section | What you choose |
|---|---|
| How many | 1 video, or 3 one after another. A topic of your own is always 1 video. |
| Topic | **Next topic in the queue**, **What is trending on the web**, **A top category**, or **My own topic** (type it in) |
| Languages | One video per language from the same topic and pictures. Each extra language costs about $0.02 and is a separate upload. |
| Look and sound | Picture quality and style, narrator, and whether a batch of 3 shuffles narrators |
| Upload | Who can watch it (public, unlisted, private, or none to keep the video on your computer) and **Review the video before it uploads** |

The **This run** box on the right shows an estimate that updates as you change the form, how many of today's 3 upload slots are
left, and a warning if you chose public with no review, or if YouTube is not connected.

## Confirm, then start

Pressing **Make video** does not start anything yet. It shows what the run will cost and what will happen to the video, and
asks you to press **Start and spend**. Only then does the run start.

!!! warning
    The cost shown is an estimate. Longer scripts, retries and extra languages can change it a little. The real cost appears
    on the run page as it grows.

## When it will not start

| Message | What to do |
|---|---|
| Add your OpenAI key first | Save it on the [Connections page](/connections) |
| A video is already being made | One run at a time. Open it, wait for it, or cancel it. |
| Today's limit is 3 videos pushed to YouTube | Try again tomorrow, or make fewer videos |

## Watching a run

After you confirm, you are taken to the run page at `/runs/<id>`. It updates every second.

- **Steps:** Choose the topic, Write the script, Draw the pictures, Record the narration, Build the video, Your review (if on),
  Upload to YouTube (if uploading). The current step spins; finished steps are ticked.
- **Progress bar and cost:** the red bar fills as steps finish. Cost so far is the real cost reported by the services.
- **Details:** open it to read the full log of what is happening.
- **Batches and languages:** a "Video 2 of 3" label shows which video is being made, and the language when you chose more than one.
- **Cancel run:** stops the run and everything it started. Money already spent stays spent. The topic is marked interrupted, and
  you can return it to the queue on the [Topics page](/docs/topics).

You can close the tab and come back. The run keeps going, and `/runs/<id>` shows where it is. The Library lists recent runs.

## Review before upload

When review is on, the run pauses after each video is made and shows:

- a player with the finished video,
- the **title**, **description** and **tags**, ready to edit,
- **who can watch it**, pre-filled from your choice.

Then:

- **Upload to YouTube** uploads it with your edits.
- **Skip upload, keep the video** leaves it on your computer, in the [Library](/docs/library).

With a batch or several languages, the run asks once per video. The run waits for you for up to 6 hours, then keeps the video
without uploading.

To skip the review, turn off **Review the video before it uploads** on the Create page for one run, or in [Settings](/docs/settings)
for every run.

## After it finishes

The run page lists each video with its cost and a link to watch it on YouTube. Videos that were not uploaded show where they are kept.

## Same thing from the terminal

The terminal has no review step. `aieye run -1 -def` makes and uploads as your saved privacy says. See [Terminal commands](/docs/terminal).
