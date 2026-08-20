import Link from "next/link";

export default function PrivacyPage() {
  return <main className="legal-page">
    <nav><Link className="brand" href="/app">PORNSCRAPER BY PORN-PROS</Link><Link href="/app">Volver a la app</Link></nav>
    <article>
      <p className="eyebrow">DOCUMENTO OPERATIVO · REVISIÓN LEGAL PENDIENTE</p>
      <h1>Política de privacidad</h1>
      <p>Vigencia: 17 de agosto de 2026. Esta política describe el funcionamiento actual y requiere revisión legal antes del lanzamiento comercial.</p>
      <h2>Datos que tratamos</h2>
      <p>Cuando creás una cuenta, tratamos tu email, identificador de autenticación, estado de plan y créditos. Para proteger el servicio de abuso, registramos un identificador de red derivado mediante hash de la IP, navegador y un identificador técnico opcional; no almacenamos esos valores originales en ese identificador. También conservamos metadatos operativos de los trabajos, como enlace enviado, estado, fecha, formato y archivo temporal.</p>
      <h2>Para qué los usamos</h2>
      <p>Usamos estos datos para iniciar sesión, asignar créditos, procesar solicitudes, prevenir abuso y fraude, administrar suscripciones, atender soporte y mejorar estabilidad y seguridad. No vendemos datos personales.</p>
      <h2>Proveedores</h2>
      <p>Según la configuración vigente, intervienen proveedores de autenticación, correo, cobro, hosting y protección de red, incluidos Supabase, Mailgun, Mercado Pago y los proveedores de infraestructura contratados. Cada proveedor procesa datos conforme a sus propias condiciones y acuerdos aplicables.</p>
      <h2>Conservación y seguridad</h2>
      <p>Los archivos de salida se mantienen de forma temporal. Los datos de cuenta y registros de seguridad se conservan solo durante el tiempo necesario para prestar el servicio, cumplir obligaciones y prevenir abuso. Aplicamos controles técnicos razonables, pero ningún sistema es completamente infalible.</p>
      <h2>Tus derechos</h2>
      <p>Antes del lanzamiento, configurá el correo de privacidad de PornScraper by Porn-Pros para solicitudes de acceso, actualización, rectificación o eliminación de datos. Para Argentina, estos derechos se interpretan junto con la <a href="https://www.argentina.gob.ar/normativa/nacional/ley-25326-64790/texto" target="_blank" rel="noreferrer">Ley 25.326 de Protección de Datos Personales</a>.</p>
      <h2>Cambios</h2>
      <p>Podemos actualizar esta política. Si el cambio es material, solicitaremos nuevamente la aceptación de la versión vigente antes de continuar usando funciones que la requieren.</p>
      <p>Leé también los <Link href="/terminos">Términos de uso</Link> y el proceso de <Link href="/dmca">reclamos de copyright</Link>.</p>
    </article>
  </main>;
}
