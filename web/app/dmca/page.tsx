import Link from "next/link";

export default function DmcaPage() {
  return <main className="legal-page">
    <nav><Link className="brand" href="/app">PORNSCRAPER BY PORN-PROS</Link><Link href="/app">Volver a la app</Link></nav>
    <article>
      <p className="eyebrow">DOCUMENTO OPERATIVO · REVISIÓN LEGAL PENDIENTE</p>
      <h1>Reclamos de copyright</h1>
      <p>PornScraper by Porn-Pros no está diseñado para alojar archivos de forma permanente: procesa archivos temporalmente para su entrega. No permitimos el uso del servicio para eludir medidas de protección, autenticación, pagos o controles de acceso de terceros.</p>
      <h2>Cómo reportar</h2>
      <p>Antes del lanzamiento, configurá el correo legal definitivo para recibir reportes con: identificación de la obra protegida; URL o identificación del material reclamado; datos de contacto; declaración de buena fe; declaración de exactitud bajo responsabilidad; y firma física o electrónica.</p>
      <h2>Respuesta</h2>
      <p>Evaluaremos reportes completos, podremos deshabilitar temporalmente material o cuentas cuando corresponda y podremos pedir información adicional. Este proceso no implica que PornScraper by Porn-Pros afirme tener protección legal específica en una jurisdicción determinada.</p>
      <h2>Antes del lanzamiento</h2>
      <p>La empresa debe definir un agente de copyright, procedimiento de contranotificación, plazos, jurisdicción y contacto legal definitivo. Si el modelo apunta a EE. UU., la estrategia debe revisarse con asesoría especializada y, si corresponde, con el directorio oficial de agentes DMCA.</p>
      <p>Leé los <Link href="/terminos">Términos de uso</Link> y la <Link href="/privacidad">Política de privacidad</Link>.</p>
    </article>
  </main>;
}
