# Conversation mode and small moments of delight

Home → **Conversation mode** starts a two-adult, two-language conversation. Each participant chooses a language before the session starts. Person A uses the warm accent and Person B the green accent, with explicit A/B labels and language names so colour is not the only cue.

Tap to record and tap to finish, with a 60-second recording cap. **Type instead** supports an accessible text turn of up to 6,000 characters. Existing audio files use the existing 3-minute/10 MB API limits. Both people should agree before recording. There is no continuous microphone listening or automatic recording on handoff.

Recorded turns use the existing upload/job API and note allowance. Typed or corrected turns use the existing translation endpoint and its separate allowance. The recognition text and spoken language can be corrected. Changing either clears approval and hides the stale translation until it is updated. A different detected speaker language must be explicitly chosen for that participant before handoff; it is not silently used to change the return direction.

After **I checked the original words, names and numbers**, **Show Person B/A** displays a large handoff screen. The recipient reads the complete translation or explicitly chooses **Generate & play AI voice**. Voice generation uses the existing read-aloud allowance and stock Gnani voice; it never starts automatically. Text over 900 characters remains fully visible but is not silently shortened for voice playback. Playback errors are visible, and leaving the handoff stops playback and ignores late responses. **Reply in…** switches the speaker and reverses the translation direction.

Conversation history is held only in the mounted screen. Leaving asks for confirmation; reloading or leaving clears its messages and recordings. Each turn is translated independently; history is not sent as hidden model context. An accepted audio turn's session receipt adds only the language pair and active speaker, with no names, transcript, history or audio. Resume polls the same job, restores the right conversation direction and consumes the receipt after success. Transient polling errors retain the receipt and offer Resume inside the conversation, preserving earlier on-screen turns. Expired/terminal jobs clear the receipt. Corrupt direction metadata falls back to the ordinary result flow rather than mislabelling a translation.

## Other changes

- A decorative waveform resolves into **Ready to check** when results arrive. Complete text is immediately available; this is not simulated live transcription or invented processing progress.
- Actual backend stages remain visible, with the correct target language. Updates say **Translating…** while in progress.
- Checked details have a short, gentle tick animation. All new motion respects `prefers-reduced-motion`.
- **Gentle sounds** in Settings is off for both new and existing users until explicitly enabled. Short tones are generated locally, without files, network calls or microphone access. Blocked sound never interrupts the workflow.
- Saved-card titles now explicitly invite a nickname. The existing 80-character title, search, update and device-only storage model are retained.
- **Try a little scenario** opens three clearly fictional, synthetic audio samples: the existing Bengali site delivery, a Hindi–English college project and Malayalam–English weekend plans. Local preview makes no AI call. **Understand this note** uses the normal upload/allowance and live processing. Results from a demo offer **Try a different scenario**. The scenario ID survives an accepted job's refresh receipt, without preserving transcript text.
- The two new stock-voice recordings are approximately 7.84 and 7.52 seconds. Their scripts and synthetic provenance are in [demo-scripts.json](demo-scripts.json). Native-speaker review remains appropriate before making language-quality claims.
- Microphone acquisition is exposed as a pending state so competing input actions cannot start while permission is being requested.

## Verification

41 frontend regression tests pass, including speaker reversal, exact edited-word handoff gating, unavailable-model honesty, target consistency, private-data exclusion from receipts, known-demo-ID validation and sound preference migration. All 96 backend regression tests pass. ESLint, TypeScript and production build pass.

Browser checks used fictional material and the existing live local Gnani/Gemini integration:

- Processed the Hindi–English audio through speech recognition and translation. The original words, three-slide quantity and instruction not to send the final file were exposed for checking.
- Translated a typed Hindi turn into English, changed 60 to 65 and verified approval was cleared, the stale translation hidden and handoff disabled. Updating preserved the corrected quantity and payment condition.
- Handed the checked result to Person B, explicitly requested voice generation, switched to English input and translated a confirmation back into Hindi. The two-turn history remained on screen.
- Refreshed immediately after an audio job was accepted. Home offered Resume, blocked another note, then restored the turn in Conversation mode using the same job. An intentionally mismatched Bengali recording exposed the detected-language warning.
- Checked the handoff at a 390px viewport without horizontal overflow. [Mobile handoff evidence](evidence/conversation-handoff-mobile.png).

Physical microphone permissions/recording on Android and iPhone, audible sound/playback behaviour and native-language quality still need real-device/human review. The five-adult trial in [INSTALLABLE-RELEASE.md](INSTALLABLE-RELEASE.md) remains unperformed; automated or synthetic tests are not substitutes.

Additional browser checks confirmed that changing the interface language after a recovered job does not replay it over edited words, the sound setting starts off and can be explicitly toggled, and the Malayalam weekend sample preserves Sunday, 9 AM, four people and its rain condition in Hindi. The result's scenario-switch button reopened the gallery with the last scenario identified. [Gallery evidence](evidence/scenario-gallery-mobile.png).

A handoff can be returned to **Check this turn again** without duplicating its history entry. A recording finished while offline or newly blocked by a limit is kept on screen as unsent and requires an explicit Send action; recordings are never silently re-uploaded. Retrying a failed accepted job only polls its receipt.

No new backend endpoint, SQL table, cloud conversation history, account, background reminder, public leaderboard or automatic social sharing is introduced.
