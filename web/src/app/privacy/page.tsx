import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy · Kettu" };

export default function PrivacyPage() {
  return (
    <main className="shell stack" style={{ gap: 20 }}>
      <Link href="/" className="wordmark">Kettu <span lang="ml">കേട്ടു</span></Link>
      <h1 className="display">Your notes, and where they go</h1>
      <p className="lede">Kettu helps you understand a voice note and reply in another language. It does not read your WhatsApp chats.</p>
      <section className="card stack">
        <h2 className="title">What gets sent</h2>
        <p>When you submit a note, the API sends its audio to Gnani AI for transcription. Transcript and reply text go to Google Gemini, or Anthropic if the operator enables that provider. Gnani makes the reply audio using a stock AI voice.</p>
        <p>Sharing a note here takes it outside WhatsApp’s end-to-end encrypted chat. Only submit notes you have permission to share. For this demo, use fictional names and details; avoid private or confidential recordings.</p>
      </section>
      <section className="card stack">
        <h2 className="title">What Kettu keeps</h2>
        <p>Uploaded audio is held in a temporary folder while queued or processing, then deleted when the job ends. Server results are held in memory for up to 10 minutes after processing. WhatsApp reply sessions expire after 15 minutes; Twilio reply audio links expire after 10 minutes.</p>
        <p>Your current note and result can remain on screen until you clear them or close the page. A note received through the installed app’s Share menu is temporarily cached on your device until it is picked up. Unclaimed shares older than 10 minutes are rejected and cleaned up when the app or share handler next checks them.</p>
        <p>A random device ID, language preferences, consent choice and spelling hints are saved in your browser. The backend may save usage counts, durations, languages and feedback in Supabase. Bot language preferences use a salted hash of the phone number. Audio and transcripts are not written to that database.</p>
        <p>Vercel, Render and messaging providers may keep their own operational logs or messages. Downloaded files and copies you share stay wherever you save or send them.</p>
      </section>
      <section className="card stack">
        <h2 className="title">AI providers have their own rules</h2>
        <p>Kettu’s temporary storage limits do not control a provider’s retention. Google’s unpaid Gemini API services may use inputs and outputs to improve products and allow human review. The operator must verify the API plan before accepting personal recordings.</p>
        <p><a href="https://ai.google.dev/gemini-api/terms">Google Gemini API terms</a> · <a href="https://www.gnani.ai/">Gnani AI</a> · <a href="https://privacy.anthropic.com/">Anthropic privacy</a></p>
      </section>
      <section className="card stack">
        <h2 className="title">Check before acting or sending</h2>
        <p>Speech recognition, translations and order lists can be wrong. Check names, quantities, dates and amounts against the original audio. Read the back-translation before making a reply. The generated voice is AI speech, not the original speaker.</p>
      </section>
      <Link href="/" className="btn btn-primary">Back to Kettu</Link>
    </main>
  );
}
