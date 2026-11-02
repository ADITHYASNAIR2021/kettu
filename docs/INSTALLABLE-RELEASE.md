# Kettu: installable, checked communication

## What changed

The header offers **Install Kettu** during onboarding, on Home and while using the app. Settings also includes it. Startup registers the production service worker and listens for installation and connection changes. A supported browser prompt is used when available; otherwise installation help explains Android Chrome, iPhone/iPad Safari or desktop Chrome/Edge. An accepted prompt alone never claims the app is installed.

`npm run build` runs Next.js, then generates `public/pwa-worker.js` and its asset inventory from the tracked `src/pwa/worker.js` template. The build ID versions the shell cache. The generated inventory includes the public HTML, current JS/CSS/font assets, manifest and icons. `/sw.js` imports that generated worker; both scripts bypass HTTP caching. Incomplete precaching fails installation. Activation retains one earlier shell cache for open pages, expires abandoned shares and preserves other applications' caches and IndexedDB. API responses and recordings never enter this public shell cache. The separate token-isolated Share cache retains its existing upload limit and ten-minute cleanup.

**Save on this device** opens an explicit privacy notice and title field. IndexedDB stores at most 50 cards, including the actual edited task, quantity, person, timing and completion states, title, source/reading language codes and timestamps. Recordings, transcripts and source quotations are excluded by a whitelist projection. Unknown details remain empty. Existing cards can be updated at the limit. Storage failures never display success. Home's **Saved cards** supports title/task search, editing, copying, plain-text export and confirmed deletion. Other people sharing the browser profile can read cards; clearing browser data can remove them.

**Prepare confirmation** works from a current or saved card. Select fields across tasks and edit the locally assembled draft. Unspecified fields are omitted; quantities, names, timing, conditions and negation are copied exactly. No AI drafting request or inferred promise is added. The composer receives explicit source and target languages from the card, independent of changed preferences. Above 700 source characters, continuation is blocked with instructions to shorten the draft or select fewer details; no fact is silently truncated. Translation, back-translation, explicit voice approval and manual sharing reuse the existing flow. Local card tools and drafting remain useful offline; AI actions require a connection.

Once an upload is accepted, its ID, reading language and submission time are saved in session storage. After refresh, Home offers **Resume processing**, which only polls that job. Back retains the receipt and one pending note blocks a second note submission. Completion, terminal error, expiration or explicit forgetting clears the receipt. Forgetting does not cancel server processing. An ambiguous upload failure never causes automatic resubmission. Audio and result text are never persisted in the receipt. Backend restarts can invalidate receipts because job results remain in memory.

## Verified locally on 2 November 2026

- 32 frontend regression tests: IndexedDB persistence/projection, independent checkmarks, concurrent limit enforcement, updates/deletion, storage denial, receipt projection, GET-only recovery, expired jobs, offline request blocking, confirmation fixtures and PWA/share caching.
- 96 backend tests pass, retaining review/action extraction regressions.
- ESLint, TypeScript and production build pass. Current build precaches 49 public assets.
- `npm audit --omit=dev`: zero reported advisories. Full audit reports 16 moderate development dependency findings through the ESLint/minimatch chain; the suggested forced downgrades were not applied. These dependencies are not in the shipped runtime.
- Browser: install help on onboarding and in Settings; fictional Bengali sample accepted once, refreshed and resumed via the same job ID. API logs showed one POST followed by GET polling, without another upload.
- Browser: edited card saved, reloaded, found through task-text search and reopened with its 60-bag quantity, timing and completion state. The receipt was consumed after success.
- Browser: confirmation omitted an unspecified person; an 841-character Indic draft retained its final fact and blocked continuation. After changing the reading preference to Hindi, the saved English card still opened an English-source/Bengali-target reply composer.
- Browser: application reopened and saved cards remained accessible after stopping the production web server. This checks shell/network-failure fallback, not airplane-mode UI detection. A subsequent production rebuild retained the saved card and displayed the changed UI. Physical installation and worker upgrade timing on each browser remain checks below.
- Responsive check: 390px viewport, no horizontal overflow (375px content width with scrollbar). [Saved card and confirmation screenshot](evidence/pwa-saved-confirmation-mobile.png).

## Fixtures and usability trial

The 12 fictional scripts and expected checked fields are in `web/tests/fixtures/communication.json`: three each in English, Hindi, Malayalam and Bengali, including quantities, fictional names, dates/timing, code-mixing, negation and conditional instructions. Automated tests verify local drafting preserves checked values; they do not establish STT, translation or native-language accuracy. The `noise` flag identifies scripts to record with background noise in the manual trial; it is not an audio-noise test result.

Recruit five consenting adults, mixing personal and work communication scenarios. Use fictional details only. Ask each person to install/open Kettu, understand one unfamiliar-language note, correct a quantity, save/reopen the card, prepare and check a confirmation, then export/delete the test card. Do not send test messages to real contacts. Use two or three fixtures per person so all 12 scripts are covered. Record:

| Participant | Device/browser | Install success | Unassisted tasks completed | Corrections needed | Seconds to checked reply | Failure observed |
|---|---|---|---|---|---|---|
| Adult 1 | Pending | Pending | Pending | Pending | Pending | Pending |
| Adult 2 | Pending | Pending | Pending | Pending | Pending | Pending |
| Adult 3 | Pending | Pending | Pending | Pending | Pending | Pending |
| Adult 4 | Pending | Pending | Pending | Pending | Pending | Pending |
| Adult 5 | Pending | Pending | Pending | Pending | Pending | Pending |

The trial has not been run. Have native speakers check the scripts, localized UI and translated replies. Investigate lost facts, mistaken commitments, installation failures and corrections before adding features or claiming market demand.

## Release and remaining device checks

Feature release `874eb67f702907ac170a24eff76e887e948aa734` was pushed to the existing `main` branch. Vercel reported deployment success, and the public site at `https://kettu-gnani.vercel.app/` displayed Install Kettu and Saved cards. Its generated asset inventory and worker used the same production build ID, with no unexpanded template placeholders and `no-store` worker headers. [Live installation guide](evidence/pwa-install-live.png).

The deployed Render API returned healthy status, exposed the review/job routes and allowed the exact Vercel origin in a CORS preflight. The deep health endpoint reported Gnani, LLM and Supabase healthy. One fictional live review extracted “60 bags”, “Maya” and “tomorrow at 8 AM”, preserved “do not pay before delivery” as a separate task, and left unspecified fields empty. This verifies deployment and one model response; it is not a general accuracy guarantee or a test of voice generation quality.

Deploy the pending backend review route and web changes together through the existing GitHub/Vercel/Render setup. Vercel's root directory stays `web`, build command `npm run build`, and `NEXT_PUBLIC_API_URL` must point to `https://kettu-api.onrender.com`. Render must allow the exact deployed origin and use one backend process. No SQL migration is required. A PWA already installed from an older deployment does not prove these features are live.

- Android Chrome: production installation, standalone launch, WhatsApp/audio Share menu, oversize/expired shares.
- iPhone/iPad Safari: Add to Home Screen, standalone launch and file upload; do not assume Android share-target support.
- Desktop Chrome: native install prompt/menu and standalone launch.
- Each platform: open online once, airplane-mode reopen, saved-card edit/save/export, disabled AI actions, reconnection, worker upgrade while preserving cards, storage denial and confirmed deletion.
- Recovery: refresh during polling; transient disconnection; expired result/backend restart; Back then Resume; Forget without claiming server cancellation. Never upload again automatically.

Keep guest access and the existing quotas. Accounts, cloud sync, subscriptions, team permissions, native apps, background reminders and phrase-level audio alignment remain outside this release. Positioning is a hypothesis: understand a voice note, check important details and answer in the sender's language. Demand is not yet proven. Before broad personal use, verify provider eligibility and data handling under the [Gemini Developer API terms](https://ai.google.dev/gemini-api/terms); this hackathon demonstration uses fictional, consented material and is adult-facing.
