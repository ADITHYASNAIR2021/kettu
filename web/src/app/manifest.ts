import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Kettu: voice notes, understood",
    short_name: "Kettu",
    description: "Read any WhatsApp voice note in your language. Reply with a voice note in theirs.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#f6efe4",
    theme_color: "#b5452b",
    categories: ["communication", "productivity", "utilities"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    // WhatsApp → Share → Kettu. The service worker (public/sw.js) catches this POST.
    share_target: SHARE_TARGET,
  };
}

// Next's type models `files` as a DOM File; the manifest spec wants {name, accept} descriptors.
const SHARE_TARGET = {
  action: "/share-target",
  method: "POST",
  enctype: "multipart/form-data",
  params: {
    files: [{ name: "audio", accept: ["audio/*", ".opus", ".ogg", ".oga", ".m4a", ".mp3", ".wav", ".aac", ".amr"] }],
  },
} as unknown as MetadataRoute.Manifest["share_target"];
