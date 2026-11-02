# Checked notes and action cards

The web result flow supports transcript correction, optional action cards and editable replies. The backend model schema also supports action extraction for order-mode notes. The WhatsApp bot does not yet expose an interactive transcript or card editor.

## Correct and retranslate

Open **Correct the transcript** under the transcript. Edit the recognized words and, if necessary, the language spoken in the recording. **Update translation & action card** regenerates the translation, summary, extracted details and action card from those words. It makes no speech-recognition or voice-synthesis call.

The original audio and original recognition text remain available for comparison. The result labels user-corrected text, and the original recognition can be loaded back into the editor. A failed request leaves the existing result and the unsaved correction intact. Leaving the result aborts the browser request so a late response cannot replace a different note.

## Editable action card

For notes without an existing card, open **More options → Make an action card** to extract up to eight explicitly requested tasks. Each task has a description, quantity, responsible person and timing. Missing or ambiguous details must be empty; relative dates remain as spoken. The server rejects a task without a source quote in the current transcript and blanks individual details without a matching quote.

This is a source-span check, not proof of semantic accuracy. The interface exposes the quoted words and lets the user correct each field, add or remove tasks, mark tasks done and copy the current card. User-edited fields drop their model source quotation. No external task, calendar entry or message is created.

The ordinary listening flow keeps its existing cheap path. Cards are generated on request or alongside order extraction, rather than adding another AI call to every voice note. Corrections regenerate the card, replacing any card edits as explained in the editor.

## Replies and optional tools

The translation and primary reply action appear first. The automatic clarification-template panel and rating prompt have been removed. Users can write a question directly in the editable reply composer, or prepare a confirmation from a checked action card.

The reply composer handles translation, back-translation, approval and optional Gnani voice synthesis. Original audio, source-word highlighting and transcript correction are grouped under **What they said**. Extra translation languages, empty-card creation and alternate-language voice export are grouped under **More options**. Opening these groups makes no AI request. Missing-fact warnings remain visible outside them.

## API and data

`POST /v1/notes/review` accepts `text` (1–6000 characters, excluding whitespace-only input), optional supported `source_lang`, supported `my_lang`, bounded `duration_s`, `mode` (`listen` or `orders`) and a valid `device_id`.

It uses the existing translation allowance and service operation cap. The response contains interpretation fields and `action_items`; it makes no new claim about recognized audio or its duration. The frontend merges it into the current result while preserving original audio provenance. Usage logging contains numeric/token metadata and language codes, not corrected text or action content.

There is no new database table or migration. Unsaved cards and corrections belong to the current browser result. Explicitly saved cards now survive reload in device-only IndexedDB; see [the installable product release](INSTALLABLE-RELEASE.md). A valid live LLM is required for model extraction; mock mode does not fabricate action cards. Manual card editing remains available.

## Verification

- Backend regression suite: 96 tests pass, including 16 review/action cases covering no extra speech calls, missing details, source grounding, malformed output, input validation, quotas, failure recovery and mock-mode honesty.
- Frontend lint, production build and TypeScript pass; all four PWA regression tests pass.
- A browser test with the real Gnani/Gemini setup changed the Bengali sample from fifty to sixty bags and verified the updated English translation. The action card was edited, checked off and copied; independent completion state was verified. A quantity clarification produced Bengali text and an English back-translation while voice generation stayed pending approval.
- Mobile layout was checked at a 390 px viewport with no horizontal overflow. [Feature preview](evidence/feature-action-card-mobile.png).
- Native speakers should review the wording of localized labels and clarification templates before a broad language rollout.

Deploy the updated backend before or together with the web app. The new review flow needs the new API route and structured model schema. Existing deployments remain unchanged until redeployed.
