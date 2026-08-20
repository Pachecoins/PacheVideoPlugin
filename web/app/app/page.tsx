import type { Metadata } from "next";
import DownloaderApp from "../components/downloader-app";

export const metadata: Metadata = {
  title: "PornScraper by Porn-Pros · Contenido público",
  description: "Procesá videos públicos autorizados desde un enlace. No admite contenido privado, pago o protegido.",
};

export default function AppPage() {
  return <DownloaderApp />;
}
