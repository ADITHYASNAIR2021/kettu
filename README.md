# Kettu (കേട്ടു) · Indian-language voice notes, understood and answered

Share any WhatsApp voice note to Kettu and get it back as text in your language, a two-line gist when it is long, and a one-tap voice reply spoken in the sender's language.

Built for the Great Indian AI Internship Challenge on **Gnani Prisma v3.0** (speech to text, auto language detection, code-mixed output) and **Gnani Timbre v3.0** (text to speech). Translation, gists and order lists run on a hosted LLM (Claude Haiku 5.5 by default; Gemini Flash behind the same switch).

Architecture, flows and trade-offs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Review findings, verification evidence and remaining deployment work: [docs/REVIEW.md](docs/REVIEW.md).

## From a note to a checked action

After reading a note, use **Correct the transcript** to fix a misheard word or the spoken language and update the translation. **Make an action card** pulls out tasks with quantities, responsible people and timing; missing details stay blank. Every suggested field has source words you can check, and the card can be edited, checked off and copied.

**Need to check a detail?** opens a date/time, quantity or repeat question in the reply composer. Edit the question, review its translation and back-translation, then choose whether to make a voice reply. Nothing is sent automatically.

Cards and corrections stay in the current result, without adding database storage. Details and verification: [docs/FEATURES.md](docs/FEATURES.md).

```
web/       Next.js 16 PWA (share target, upload, recorder, reply flow) → Vercel
backend/   FastAPI API + WhatsApp bot (ffmpeg, Prisma, Timbre, LLM, queue, limits) → Render
scripts/   deploy-backend.sh, make_icons.py
```

## Two ways to use it on your own WhatsApp

**A. Share sheet (no Meta setup).** Open the web app on Android Chrome → *Add to home screen*. Now in any chat: long-press a voice note → Share → **Kettu**. Tap *Reply in Bengali*, speak or type in your language, check the back-translation, tap *Make voice note* → *Share to WhatsApp* → pick the chat. On iPhone and desktop, upload or drag the audio file instead.

**B. Kettu as a WhatsApp contact.** Forward any voice note to the Kettu number. It replies in the same chat with the translation and gist; *Reply in …* gives you back a voice note in their language to forward on. Two ways to connect it:

* **Twilio sandbox**: no Facebook account needed. Menus are numbered ("reply 1"). Setup below.
* **Meta Cloud API test number**: tap buttons and real voice-note bubbles, but whoever creates the Meta app needs a Facebook account.

---

## Run locally (no keys needed)

Requirements: Python 3.11+, Node 20+, ffmpeg on PATH.

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # macOS/Linux: .venv/bin/pip
cp .env.example .env.local                             # keys go here; empty keys → mock speech / mock LLM
.venv/Scripts/python -m uvicorn kettu.main:app --app-dir src --port 8000
```

```bash
cd web
npm install
cp .env.example .env.local                             # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm run dev                                            # http://localhost:3000
```

Mock mode runs the whole product (queue, limits, chunking, UI, reply audio) with canned transcripts and a beep instead of a voice. Put real keys in `backend/.env.local` (it overrides `backend/.env`) to go live. On Windows, use `127.0.0.1` rather than `localhost` for the API URL: `localhost` tries IPv6 first and adds about 2 s per request.

| Variable | Where to get it |
|---|---|
| `GNANI_API_KEY` | app.gnani.ai → API keys (5,000 programme credits) |
| `ANTHROPIC_API_KEY` | console.anthropic.com (or `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Supabase project (Mumbai) → run `backend/sql/schema.sql` once |

Tests (real ffmpeg, mocked models and WhatsApp):

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

## Set up the WhatsApp bot with Twilio (no Facebook account)

1. Sign up at twilio.com (email + phone; trial credit included). On the onboarding screen pick *Messaging*, *With code*.
2. Console home → copy **Account SID** and **Auth Token** into `backend/.env.local` as `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`. Put your own number in `WA_ALLOWED_NUMBERS` (country code, no `+`).
3. Console → Messaging → Try it out → **Send a WhatsApp message**. From your WhatsApp, send the `join <two-words>` code shown there to the sandbox number (+1 415 523 8886). Save that number as "Kettu".
4. Start the API, then a tunnel to it: `ngrok http 8000` (or `cloudflared tunnel --url http://localhost:8000`). Put the `https://…` address in `PUBLIC_API_URL` and restart the API.
5. In the same Twilio sandbox page → *Sandbox settings* → **When a message comes in**: `https://<that address>/twilio/webhook`, method `POST` → Save.
6. Send "hi" to Kettu on WhatsApp, reply with the number of your language, then forward voice notes to it.

**Trial accounts in the new Console** get a "Try out WhatsApp" number (e.g. +1 737 250 8034, `join twilio-trial`, 100 free messages) that cannot call a webhook. Use it with `TWILIO_MODE=poll` and `TWILIO_WHATSAPP_FROM=whatsapp:+1737…`: Kettu reads new messages from Twilio's API every 2 seconds, so step 5 is skipped (the tunnel is still needed so Twilio can fetch reply audio). Twilio also sends its own "Standard auto-reply" after each message on this number; ignore it.

Sandbox notes: only numbers that sent the `join` code can use it, and after a few days of silence you send `join` again. The tunnel address changes every time you restart a free tunnel, so update steps 4–5 when it does (or deploy the API and use its fixed URL).

## Set up the WhatsApp bot with the Meta Cloud API (needs a Facebook account)

1. **Meta app.** developers.facebook.com → *Create app* → type *Business* → add the **WhatsApp** product. Meta gives you a free **test phone number** and a temporary access token.
2. **Allow your number.** WhatsApp → API Setup → *To* → add your own number and confirm the code. The test number can message up to 5 verified numbers.
3. **Permanent token.** Business Settings → System users → add one with `whatsapp_business_messaging` and `whatsapp_business_management` → generate a token. Put it in `WA_ACCESS_TOKEN`. Copy the *Phone number ID* into `WA_PHONE_NUMBER_ID` and *App settings → Basic → App secret* into `WA_APP_SECRET`. Choose any long random `WA_VERIFY_TOKEN` and `WA_HASH_SALT`. Set `WA_ALLOWED_NUMBERS` to your number (country code, no `+`).
4. **Public HTTPS URL.** Deploy the API (below), or for local testing run a tunnel: `cloudflared tunnel --url http://localhost:8000`.
5. **Webhook.** WhatsApp → Configuration → Callback URL `https://<api>/whatsapp/webhook`, Verify token = `WA_VERIFY_TOKEN` → *Verify and save* → subscribe to the **messages** field.
6. **Use it.** Save the test number as "Kettu" in your contacts and send "hi". Pick your language, then forward voice notes to it.

Commands inside the chat: `help`, `language`, `voice` (female/male reply voice), `orders` (next note becomes a checklist), `cancel`.

Going beyond 5 numbers needs Meta business verification and a real number; the PWA (option A) has no such limit.

## Deploy

**API → Render (free, no card).** Push this repo to GitHub, then Render → *New* → *Blueprint* → pick the repo. [render.yaml](render.yaml) creates one free Docker service in Singapore and asks for `GNANI_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` and `CORS_ORIGINS` (your Vercel address). The free plan sleeps after 15 minutes idle and takes about a minute to wake; the app says so on screen. During launch week, point a free uptime monitor (e.g. UptimeRobot, every 5 minutes) at `https://<service>.onrender.com/healthz` to keep it awake.

**Web → Vercel.** *Add New* → *Project* → import the same repo, **Root Directory `web`**, environment variable `NEXT_PUBLIC_API_URL=https://<service>.onrender.com`, deploy. Then put the Vercel address into Render's `CORS_ORIGINS`.

**Alternative: API → Cloud Run (Mumbai)**, closest to Gnani's servers, needs a billing account. Create the secrets listed at the top of [scripts/deploy-backend.sh](scripts/deploy-backend.sh) (drop the `WA_*` ones from `--set-secrets` if you skip the bot), then:

```bash
PROJECT=<gcp-project> WEB_ORIGIN=https://<your-app>.vercel.app SUPABASE_URL=https://<ref>.supabase.co ./scripts/deploy-backend.sh
```

One instance (min 1, max 1) on purpose: the job queue and the Gnani request gate live in that process. Render or Railway work the same way with the same Dockerfile.

**Monitoring.** Point an uptime check at `/healthz` (cheap) and `/healthz?deep=1` (checks Gnani, the LLM and Supabase). Progress numbers for the post: `select * from kettu_stats;` and `select * from kettu_thumbs;` in Supabase.

## What it does well, and what it does not (yet)

The installable release adds discoverable installation, device-only saved cards, checked confirmation drafts and recovery after refresh. See [release behavior, verification and device-test checklist](docs/INSTALLABLE-RELEASE.md).

* Handles notes up to 3 minutes: split at pauses into ≤ 28 s chunks, each sent to Prisma with the previous text for context.
* Same per-person limits on both channels: 10 notes and 5 voice replies a day, plus a whole-service daily budget with a waitlist message instead of an error.
* Replies shared from the PWA arrive as an audio file, not a voice-note bubble (a WhatsApp limit); the bot sends a true voice note.
* Gists and entity chips are AI output: the app labels them as a summary and links every amount, time and name back to the exact words in the transcript.
* Uploaded audio is deleted when the job ends. API results expire after 10 minutes; browser results remain until cleared or closed. Supabase stores usage metadata, feedback and optional bot preferences. Third-party providers have their own data policies; see the app's `/privacy` page.
* Demo audio must be scripted and consented with fake names and numbers, per the contest rules.
