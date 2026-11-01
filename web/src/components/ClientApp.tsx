"use client";

import dynamic from "next/dynamic";

// Kettu keeps its settings on the phone (localStorage), so it renders in the browser only.
const KettuApp = dynamic(() => import("./KettuApp"), {
  ssr: false,
  loading: () => (
    <main className="shell">
      <div className="topbar">
        <span className="wordmark"><b>Kettu</b><span lang="ml">കേട്ടു</span></span>
      </div>
    </main>
  ),
});

export default function ClientApp() {
  return <KettuApp />;
}
