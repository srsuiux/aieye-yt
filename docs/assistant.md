# Assistant (beta)

The assistant, **Iris**, lets you make and publish videos by chatting. Tell it what you want in your own words: "make a video
about how bees make honey", "use the next topic in my queue", "what is waiting in my Library?". It checks your limits, plans the
video, shows the cost, and starts only when you press a button.

Iris is a **beta**: it is newer and tested less than the Create page, and an AI can misunderstand you.

## What you see

- **Starter cards.** On an empty chat, four cards show what they will do before you click: your next queued topic, how many
  videos you can still push today, what is waiting in the Library, and a trending search. Clicking one sends that request.
- **Voice dictation.** The microphone button next to Send turns your speech into text in the box. Nothing is sent until you press
  Send. It uses your browser's speech service, so it only appears in browsers that have one (such as Chrome and Safari).
- **A quiet header.** Iris's logo shows once per reply, not on every message. While Iris works, its logo changes colour and the
  header shows **Working**. When idle it is still. **More info** under the box opens the short list of cautions.

- **Its work, live.** While Iris works you see each step as it happens, such as "Checking your keys, daily limit and settings".
  When it finishes, the steps fold into one line ("Worked through 2 steps") that you can open again.
- **A video plan card.** It lists the topic, how many videos, languages, picture style and quality, narrator and upload choice,
  with an estimated cost. Nothing has started yet.
- **Make it.** Pressing the button on the card starts the run. The card then becomes a live tracker with the steps, the cost so
  far, a link to the full run page, and **Cancel run**.
- **Review before upload.** If review is on (the default), the finished video appears in the chat with its title, description and
  tags for you to edit. You choose **Upload to YouTube** or **Skip upload, keep the video**.
- **An upload card.** Ask Iris to upload a video from your Library and it shows the title and who can watch it. Pressing
  **Upload** starts it.

## What Iris can and cannot do

| Iris can | Iris cannot |
|---|---|
| Look at your keys, daily limit, saved defaults, topic queue, recent runs and Library | Spend money or publish by itself: every make and upload needs your button press |
| Plan a video or a batch of 3, with your defaults unless you ask for something else | Change your settings, keys, channel details or topics (it tells you which page to use) |
| Plan an upload of a video from your Library | Delete videos |

The same limits as the rest of AI Eye apply: 1 or 3 videos at a time and your daily limit on videos pushed to YouTube.

## Cost and privacy

- Chatting uses an OpenAI model that you can pick under **Settings > Advanced > Models > Assistant model**. A reply usually costs
  about half a cent with the default. The video itself costs what the plan card says.
- What you type, and the facts Iris reads about your queue, runs and Library, are sent to OpenAI to produce the reply. See
  [Privacy](/docs/privacy).
- Your chats are saved on your computer in `data/chat/`. Delete that folder to remove them.
- An AI can be wrong. Check facts before you publish, and label realistic AI content on YouTube. See [Copyright and content](/docs/copyright).

## Tips

- Say what you want, not how: "Make a video about volcanoes in Hindi and English, render only."
- If you do not name a topic, Iris asks whether to use your queue, what is trending, a top category, or your own idea.
- Use **New chat** to start fresh. Iris remembers the last few turns of a chat, not older ones.
