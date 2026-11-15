# Set up YouTube uploads

Uploading uses YouTube's official API. You create a small "client" in your own Google Cloud project, so the permission
belongs to you and no one else. This takes about 10 minutes, once.

## 1. Create a Google Cloud project

1. Open [console.cloud.google.com](https://console.cloud.google.com) and sign in with the Google account that owns your channel.
2. Choose **Select a project**, then **New project**. Name it "AI Eye" and create it.

## 2. Turn on the YouTube Data API

1. Open **APIs & Services**, then **Library**.
2. Search for **YouTube Data API v3** and press **Enable**.

## 3. Set up the consent screen

1. Open **APIs & Services**, then **OAuth consent screen**.
2. Choose **External** and fill in the app name ("AI Eye") and your email.
3. On the **Test users** step, add your own Google account.

!!! warning
    While the app is in **Testing** status, Google signs you out about every 7 days. Press **Sign in with Google** again on the
    Connections page when that happens. Publishing the app removes this limit but needs Google's review.

## 4. Create the client file

1. Open **APIs & Services**, then **Credentials**.
2. Choose **Create credentials**, then **OAuth client ID**.
3. Set **Application type** to **Desktop app**. Name it anything.
4. Press **Download JSON** on the new client.

## 5. Add it to AI Eye

1. Open [Connections](/connections), find the YouTube card, choose the downloaded file and press **Save client file**.
2. Press **Sign in with Google**, pick your channel's account and allow the upload permission.

Without the web app, save the file as `data/credentials/client_secrets.json` and start any run with uploading on. A browser
window opens once to sign in.

!!! note
    Google may restrict videos uploaded through a new, unaudited API project so they can only be private. If your uploads stay
    private even when you chose public, request an API compliance audit from Google. Until then, change the video to public by hand
    in YouTube Studio.

## Use more than one channel

The sign-in belongs to the account you chose. To switch channels, press **Sign out** on the Connections page and sign in again
with the other account.
