const windowsDownloadUrl =
  process.env.PORNSCRAPER_WINDOWS_DOWNLOAD_URL ??
  "https://github.com/Porn-Pros/PornScraper/releases/latest/download/PornScraper-Setup-Windows-x64.exe";

function Mark() {
  return <img className="brand-logo" src="/pornbros-mark.svg" alt="PornScraper" />;
}

export default function HomePage() {
  return (
    <main className="landing-shell" id="contenido">
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      <header className="marketing-topbar" aria-label="Navegación principal">
        <a className="brand" href="#inicio" aria-label="PornScraper, inicio">
          <Mark />
          <span className="brand-subtitle">PORN SCRAPER<small>BY PORN-PROS</small></span>
        </a>
        <nav className="marketing-nav" aria-label="Secciones">
          <a href="#como-funciona">Cómo funciona</a>
          <a href="#pro">Pro</a>
          <a href="#preguntas">Preguntas</a>
        </nav>
        <a className="nav-cta" href={windowsDownloadUrl} rel="noreferrer">Descargar para Windows</a>
      </header>

      <section className="landing-hero" id="inicio" aria-labelledby="hero-title">
        <div className="hero-copy">
          <span className="landing-eyebrow">ESCRITORIO · WINDOWS</span>
          <h1 id="hero-title">Tu flujo de descargas, <span>en tu propia PC.</span></h1>
          <p>PornScraper by Porn-Pros organiza descargas de contenido público o al que ya tenés acceso autorizado. Sin límites artificiales de velocidad y con reintentos cuando una fuente falla.</p>
          <div className="hero-actions">
            <a className="landing-primary" href={windowsDownloadUrl} rel="noreferrer">Descargar para Windows <span aria-hidden="true">→</span></a>
            <a className="landing-secondary" href="/app">Ver la herramienta web</a>
          </div>
          <div className="hero-proof" aria-label="Características principales"><span>Instalación local</span><i aria-hidden="true" /><span>Control de tus archivos</span><i aria-hidden="true" /><span>Contenido público o autorizado</span></div>
        </div>

        <figure className="product-preview">
          <img src="/pornscraper-desktop-preview.png" alt="Captura real de PornScraper Desktop mostrando el formulario de descarga" />
          <figcaption>Captura real de PornScraper Desktop.</figcaption>
        </figure>
      </section>

      <section className="landing-section" id="como-funciona" aria-labelledby="how-title">
        <div className="landing-section-heading"><span>FLUJO SIMPLE</span><h2 id="how-title">De un enlace a tus archivos, sin vueltas.</h2><p>Elegís lo que querés procesar, revisás la lista y decidís qué descargar.</p></div>
        <div className="steps-grid">
          <article><b>01</b><h3>Pegá o buscá</h3><p>Usá un enlace público compatible o iniciá una búsqueda desde la aplicación.</p></article>
          <article><b>02</b><h3>Revisá antes</h3><p>Previsualizá resultados y playlists; seleccioná exactamente cuántos elementos procesar.</p></article>
          <article><b>03</b><h3>Guardá localmente</h3><p>Los archivos van a la carpeta que elegís. Si una fuente falla, el proceso vuelve a intentarlo.</p></article>
        </div>
      </section>

      <section className="landing-section" aria-labelledby="features-title">
        <div className="feature-grid">
          <article className="feature-main"><span>CONTROL LOCAL</span><h2 id="features-title">Una herramienta pensada para quien necesita continuidad.</h2><p>Sin límites artificiales de velocidad: el rendimiento depende de tu conexión, tu equipo y la fuente disponible.</p><div className="server-visual" aria-hidden="true"><div><span>Enlace</span><b>→</b><span>Cola local</span><b>→</b><span>Tu carpeta</span></div></div></article>
          <article className="feature-card"><span>PREVISUALIZACIÓN</span><h3>Listas bajo control</h3><p>Mirás los resultados antes de iniciar una descarga por lote.</p></article>
          <article className="feature-card"><span>RECUPERACIÓN</span><h3>Reintentos claros</h3><p>La app reintenta errores transitorios y te deja relanzar un elemento puntual.</p></article>
        </div>
      </section>

      <section className="landing-section" id="pro" aria-labelledby="pro-title">
        <div className="landing-section-heading"><span>MEMBRESÍA</span><h2 id="pro-title">Cuando quieras más, pasás a Pro.</h2><p>La edición Pro habilita funciones avanzadas y procesamiento de listas. El precio y las condiciones se muestran antes de confirmar la suscripción.</p></div>
        <div className="landing-plans">
          <article className="landing-plan-card"><span className="landing-plan-name">EDICIÓN LOCAL</span><div className="landing-price"><strong>Para probar</strong></div><p>Instalá la herramienta y conocé el flujo desde tu computadora.</p><ul><li><span className="check-icon">✓</span>Procesamiento local</li><li><span className="check-icon">✓</span>Carpeta de destino elegible</li><li><span className="check-icon">✓</span>Reintentos ante fallos</li></ul><a className="plan-button secondary" href={windowsDownloadUrl} rel="noreferrer">Descargar Windows</a></article>
          <article className="landing-plan-card pro"><span className="recommended-badge">PRO</span><span className="landing-plan-name">MEMBRESÍA PRO</span><div className="landing-price"><strong>Más capacidad</strong></div><p>Para trabajar con listas, previsualizaciones y herramientas de selección.</p><ul><li><span className="check-icon">✓</span>Procesamiento por lote</li><li><span className="check-icon">✓</span>Previsualización de playlists</li><li><span className="check-icon">✓</span>Soporte de la membresía</li></ul><a className="plan-button" href="/app#planes">Conocer Pro</a></article>
        </div>
      </section>

      <section className="landing-section faq-section" id="preguntas" aria-labelledby="faq-title">
        <div className="landing-section-heading align-left"><span>TRANSPARENCIA</span><h2 id="faq-title">Preguntas frecuentes.</h2><p>Lo importante, claro antes de instalar.</p></div>
        <div className="faq-list">
          <details><summary>¿La landing almacena el instalador?</summary><p>No. El botón lleva directamente al archivo de instalación publicado externamente. Así la web se mantiene liviana.</p></details>
          <details><summary>¿Qué contenido puedo procesar?</summary><p>Solo contenido público o contenido para el que ya contás con autorización de acceso y descarga. No se admiten fuentes privadas, pagas o protegidas.</p></details>
          <details><summary>¿La aplicación limita la velocidad?</summary><p>No agrega una limitación artificial. La velocidad final depende de tu conexión, el equipo y la disponibilidad de la fuente.</p></details>
          <details><summary>¿Dónde se guardan mis archivos?</summary><p>En la carpeta que elegís desde la aplicación de escritorio.</p></details>
        </div>
      </section>

      <section className="final-cta" aria-labelledby="final-title"><span>LISTO PARA INSTALAR</span><h2 id="final-title">Descargalo y empezá desde tu escritorio.</h2><p>Windows 10 o posterior, 64 bits. El instalador se abre desde una ubicación externa.</p><a className="landing-primary" href={windowsDownloadUrl} rel="noreferrer">Descargar para Windows <span aria-hidden="true">→</span></a></section>

      <footer className="landing-footer"><a className="brand" href="#inicio"><Mark /><span>PORN SCRAPER<small>BY PORN-PROS</small></span></a><p>Procesá únicamente contenido público o autorizado.</p><span><a href="/terminos">Términos</a> · <a href="/privacidad">Privacidad</a> · <a href="/dmca">Copyright</a></span></footer>
    </main>
  );
}
