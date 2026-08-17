import type { Metadata } from "next";
import DownloaderApp from "../components/downloader-app";

export const metadata: Metadata = {
  title: "PacheVideo App — Preparar descarga",
  description: "Registrate gratis y prepará 5 videos hasta 1080p o audio MP3 desde un enlace.",
};

export default function AppPage() {
  return <DownloaderApp />;
}
