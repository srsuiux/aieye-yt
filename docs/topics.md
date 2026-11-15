# Topics and the queue

Open **Topics** from the left menu, or go to `/topics`.

## The queue

Videos are made from the queue, from the top down. When the queue is empty, AI Eye asks the model for new ideas.

| Control | What it does |
|---|---|
| Up and down arrows | Change the order. The topic at the top is made next. |
| Remove | Takes the topic out of the queue. |
| Return to queue | Appears on a topic marked "Being made, or interrupted". Such a topic is skipped until you return it. |

A topic that is being made cannot be removed, to protect a run that is in progress.

## Add a topic

Write the topic as a short question or sentence, and optionally a one-line hook. AI Eye checks it against everything already
made or queued. If it looks like the same animal, object or phenomenon, you see a warning with the earlier title, and you can
choose **Add it anyway**.

!!! note
    Repeats usually get far fewer views than the original, which is why the check exists. The same check runs on topics the
    model writes for itself.

## Already made

The most recent 30 finished videos, with the date. The full history is in `data/db/final.json`.
