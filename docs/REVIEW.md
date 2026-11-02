# Kettu review — 2 November 2026

Kettu translates shared or recorded voice notes between ten Indian languages and English, extracts useful details, and drafts a checked voice reply in the sender's language. The PWA and optional WhatsApp bot use the same FastAPI pipeline. Gnani performs speech recognition and synthesis; the configured hosted LLM performs translation and extraction. Supabase stores operational metadata and bot preferences, not transcripts or audio.

The repository was clean before this review. Changes are local; this review does not claim they have been deployed or that the SQL migration has been applied.

## Verified behavior

| Check | Result |
|---|---|
| Backend test suite using `backend/.venv` | 80 passed, including 25 new hardening cases |
| PWA service-worker tests | 4 passed: share redirect, separate concurrent shares, oversize rejection, cache expiry/isolation |
| Frontend lint | Passed with no warnings |
| Frontend production build and TypeScript | Passed; includes `/privacy` |
| Updated local mobile UI | No horizontal overflow at a 390 px viewport; dialog focus entry, Shift+Tab containment, Escape and return to the opener verified |
| npm production dependency audit | No known vulnerabilities |
| Python installed dependency audit | 41 packages, no skipped packages, no known vulnerabilities after fixing setuptools; [JSON report](backend-dependency-audit.json) |
| Public Vercel page | HTTP 200 at `https://kettu-gnani.vercel.app/` |
| Public Render liveness and deep health | Both HTTP 200; deep endpoint reports speech, LLM and Supabase reachable |
| Deployed speech-to-text and translation | Bengali scripted sample produced an English translation containing the time, quantities, wages, names and follow-up request |
| Deployed reply preview and TTS | Fictional English reply translated to Bengali with a back-translation; generated audio loaded successfully, duration 2.64 seconds, media ready state 4 and no media error |

The live tests exercised the previously deployed version. They establish that the existing provider path works for that sample, not that the new fixes are live or that translation accuracy is proven across every language. No messages were sent to another person. [Live voice-reply screenshot](evidence/deployed-voice-reply.png).

Updated local interface evidence: [mobile home](evidence/updated-mobile-home.png), [mobile reply dialog](evidence/updated-mobile-dialog.png).

Tests use synthetic audio and mocked external providers. The live sample and reply are separate checks. Native Android share-sheet installation, microphone permissions across real phones, actual Meta/Twilio delivery and provider account retention settings still require device/account verification.

## Faults fixed

| Area | Finding and change |
|---|---|
| Model costs | Allowances were checked before asynchronous work, allowing concurrent requests to bypass them. Added reservations for queued notes, previews, translations and voice output, including the spoken-preview speech budget. Added a service-wide operation cap independent of client-supplied device IDs. |
| Ingress | Upload size was checked after multipart parsing. Added an ASGI gate that bounds bodies including chunked requests, spools larger bodies to temporary storage, times out slow uploads, caps active requests and applies a bounded peer rate limit. |
| Upload privacy | Queue rejection, invalid preview fields and shutdown could leave files behind. Fields are validated before saving, multipart files are closed, rejection paths clean up, and the queue owns cleanup callbacks. |
| Audio safety | Added demuxer/protocol restrictions to prevent playlists from fetching URLs or arbitrary files. Bounded input decoding protects recordings with missing duration metadata. Decode timeouts become plain user errors. |
| Bot webhooks | Meta webhooks no longer accept unsigned requests when the app secret is absent. Existing signatures and deduplication remain. |
| Provider media | Added streaming download limits, HTTPS/provider host checks and redirect checks. Twilio credentials are withheld from CDN redirects. Provider response bodies are removed from messaging error logs. |
| AI facts | Removed a fallback that returned invented entities when no source text matched. A repair pass can no longer hide a missing fact by dropping its entity. Model response shape failures now produce plain errors. Prompts treat supplied text as data. |
| Reporting data | Supabase aggregate views now use `security_invoker` and revoke access from public application roles. This requires applying the updated SQL. |
| Recovery | Usage restoration paginates through database result limits. A configured database failure no longer silently resets all allowances on startup. |
| Retention | Job reads enforce expiry without waiting for the janitor. Added periodic bot/session/media cleanup and bounded in-memory feedback retention. |
| PWA shares | `Response.redirect()` previously used relative URLs. Redirects are now absolute. Separate share tokens prevent one pending note replacing another; oversized shares are rejected and expired shares are cleaned up. Only Kettu-owned obsolete caches are removed. |
| Honesty | Replaced “nothing is stored” with a privacy page and updated consent in English, Malayalam, Hindi and Bengali. The page distinguishes server, browser, database and provider retention. Hosted configuration can refuse mock models; mock transcripts are labelled. |
| Interaction | Replies now record for at most 60 seconds, matching backend acceptance. Late microphone permission resolution releases tracks after unmount. Language/text controls cannot change underneath a recording or pending preview. Dialogs move and contain keyboard focus; the underlying page becomes inert. Long buttons wrap on phones. Read-aloud audio is cleaned up and reused while the result stays open. |
| Error handling | Added request/poll deadlines, sample-loading feedback and accurate wording when returning from a job that continues in the background. |
| Dependencies | Pinned direct Python dependencies to tested versions. Updated vulnerable `setuptools` to 84.1.0 and included it in deployment requirements. Expanded Docker exclusions to cover `.env.local` and other environment files. |

## Apply the changes

1. Review and apply `backend/sql/schema.sql` in the Supabase SQL editor. Its existing table creation is idempotent; the changed view definitions and grants close the reporting exposure. The service role retains access. Re-run a public-role access check after applying it.
2. Deploy the backend changes to Render, installing the pinned requirements. Keep exactly one process/instance. Set `REQUIRE_LIVE_MODELS=true`, verify `CORS_ORIGINS=https://kettu-gnani.vercel.app`, and retain the existing model/DB credentials as secrets. Existing manually created Render services may need environment changes in their dashboard even though the Blueprint is updated.
3. Deploy `web/` to Vercel with `NEXT_PUBLIC_API_URL=https://kettu-api.onrender.com`. Open the installed PWA online so its updated service worker activates.
4. Check both health endpoints, a scripted sample, an approved synthetic reply, `/privacy`, API `Cache-Control: no-store`, CORS and signed webhook behavior on the new deployment. Try Android installation/share and iPhone file upload on real devices.

## Limits that still matter before a public launch

- Device UUIDs identify a browser installation, not a verified person. CORS is a browser control, not authentication. For a paid or widely public service, add verified identities and edge abuse controls; test proxy trust so peer limits use the intended client address. Shared networks may currently share the peer allowance.
- Queues, reservations, retries and results are process-local. Restarting loses queued jobs; multiple instances do not coordinate. Successful usage is restored from Supabase, but failed/partial provider calls and retries are not a durable spend ledger. Use provider-side spending limits now. Add a durable queue and atomic database reservations before scaling or promising strict cost accounting.
- Provider data policy must match the actual account. Google's current Gemini terms describe professional/business and adult use, and allow product improvement and human review for unpaid services; paid API projects have different data handling. Verify the target audience and billing plan before accepting personal notes. [Google's terms](https://ai.google.dev/gemini-api/terms).
- The shipped schema has no usage-metadata retention schedule. Decide and configure one before collecting ongoing real-user usage; provide an operator contact and deletion process for persistent metadata. Do not promise complete deletion from other providers or recipients.
- Grounding checks verify copied source spans, not the semantic accuracy of every translation, name, amount or order item. Keep original audio and back-translation review in the workflow. Measure quality with consenting native speakers before relying on new language pairs.
- This pass checked repository code, tests and the supplied public endpoints. It did not inspect Render/Vercel account permissions, deployment secrets, provider account settings or the live Supabase policies through an authenticated administrative connection. Container OS advisories were not scanned.

## Product and market judgment

There is a plausible need for communication across Indian languages. IAMAI/Kantar reports that 870 million users accessed the internet in Indic languages in 2024. This is evidence of language demand, not a count of Kettu customers or willingness to pay. [Internet in India 2024](https://www.iamai.in/sites/default/files/research/Kantar_%20IAMAI%20report_2024_.pdf).

WhatsApp already offers on-device voice-message transcripts. A transcription-only pitch has a strong built-in competitor and a privacy disadvantage when it sends audio to cloud services. [WhatsApp's announcement](https://blog.whatsapp.com/introducing-voice-message-transcripts).

The stronger initial offer is a multilingual coordination tool for small contractors, suppliers and field teams: understand a spoken order, check its quantities and timing, and return a voice reply the sender understands. The existing order list, source-linked details, custom spelling hints and back-translation fit this offer. Preserve the distinctive typography, native-script language selection and short action-led copy; adding generic dashboards would not establish demand.

Pilot with a small number of adult business users using consented, non-sensitive notes. Track repeat weekly use, whether users finish tasks faster, corrections to quantities/times, reply completion, latency and actual provider cost per completed conversation. Validate willingness to pay before adding billing. Useful next investments are native-speaker accuracy evaluation, correction before retranslation, durable jobs and verified team access. No unrelated features were added to the product during this review.
