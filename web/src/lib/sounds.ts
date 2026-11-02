/** Quiet local feedback only. No microphone, files or network; preference is opt-in. */
export function feedbackSound(enabled: boolean, kind: "check" | "ready" = "check") {
  if (!enabled) return;
  try {
    const context = new AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.connect(gain); gain.connect(context.destination);
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(kind === "ready" ? 620 : 740, context.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(kind === "ready" ? 830 : 920, context.currentTime + 0.09);
    gain.gain.setValueAtTime(0.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.035, context.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.14);
    oscillator.onended = () => { void context.close().catch(() => undefined); };
    void context.resume().then(() => { oscillator.start(); oscillator.stop(context.currentTime + 0.16); })
      .catch(() => context.close().catch(() => undefined));
  } catch { /* Feedback is optional; blocked audio never interrupts the task. */ }
}
