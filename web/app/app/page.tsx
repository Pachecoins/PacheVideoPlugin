import type { Metadata } from "next";
import DownloaderApp from "../components/downloader-app";

export const metadata: Metadata = {
  title: "PacheVideo App · Descargador multimedia",
  description: "Descargá video y audio desde un enlace.",
};

export default function AppPage() {
  return <DownloaderApp />;
}
