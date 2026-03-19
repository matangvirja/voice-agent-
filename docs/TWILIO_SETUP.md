# Twilio Setup Guide

## Step 1 — Create trial account

1. Go to [twilio.com](https://twilio.com) → Sign up
2. Verify your phone number via SMS — **this becomes your verified caller ID**
3. You get **$15 free credit** automatically (no credit card needed initially)

---

## Step 2 — Get a phone number

1. Twilio Console → **Phone Numbers** → **Manage** → **Buy a number**
2. Search for a US number
3. Make sure **Voice** capability is checked
4. Click Buy (~$1 from your trial credit)

---

## Step 3 — Get your credentials

From Twilio Console → Dashboard:

| Key | Where to find |
|---|---|
| Account SID | Starts with `AC...` — shown on dashboard |
| Auth Token | Click the eye icon to reveal |
| Phone Number | The number you just bought |

Add to `.env`:
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
```

---

## Step 4 — Verify your Indian mobile number

Trial accounts can ONLY call verified numbers.

1. Twilio Console → **Phone Numbers** → **Manage** → **Verified Caller IDs**
2. Click **"Add a new Caller ID"**
3. Enter your Indian mobile: `+91XXXXXXXXXX`
4. Twilio will call or SMS you with a verification code
5. Enter the code → number is verified

---

## Step 5 — Set webhook URL

When someone calls your Twilio number, Twilio needs to know where to send the request.

1. Twilio Console → **Phone Numbers** → **Manage** → **Active Numbers**
2. Click your phone number
3. Scroll to **"Voice Configuration"**
4. Under **"A call comes in"** → select **"Webhook"**
5. Enter: `https://YOUR_NGROK_URL/call/incoming`
6. Method: **HTTP POST**
7. Click **Save configuration**

> **Important:** Update this URL every time ngrok restarts (free plan gives a new URL each time)

---

## ngrok Setup

ngrok creates a public URL that points to your laptop so Twilio can reach your server.

### Install
```bash
winget install Ngrok.Ngrok
```

### Configure auth token
1. Sign up at [ngrok.com](https://ngrok.com) (free)
2. Copy your authtoken from the dashboard
3. Run: `ngrok config add-authtoken YOUR_TOKEN`

### Start tunnel
```bash
ngrok http 8000
```

You'll see:
```
Forwarding  https://abc123.ngrok-free.app → http://localhost:8000
```

Copy the `https://...` URL → update `NGROK_URL` in `.env` → update Twilio webhook.

---

## Troubleshooting

| Error | Fix |
|---|---|
| "Not a valid URL" | Using localhost — ngrok must be running and NGROK_URL set |
| Call connects but no audio | stream_sid not set — greeting must be sent after "start" event |
| Call doesn't connect | Verify target number in Twilio Console |
| 404 on webhook | Wrong ngrok URL in Twilio — update after each ngrok restart |
