import Link from "next/link";

const ArrowIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 20 20" width="18" height="18" fill="none">
    <path d="M4 10h11M11 6l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const CheckIcon = () => (
  <span className="check-icon" aria-hidden="true">
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
      <path d="m3.5 8 3 3 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </span>
);

export default function LandingPage() {
  return (
    <main className="landing-shell">
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      <nav className="marketing-topbar" aria-label="Navegación principal">
        <Link className="brand" href="/" prefetch={false} aria-label="PacheVideo, inicio">
          <span className="brand-mark">P</span>
          <span>PACHEVIDEO</span>
        </Link>
        <div className="marketing-nav">
          <a href="#como-funciona">Cómo funciona</a>
          <a href="#planes">Planes</a>
          <a href="#preguntas">Preguntas</a>
        </div>
        <Link className="nav-cta" href="/app" prefetch={false}>Abrir PacheVideo</Link>
      </nav>

      <section className="landing-hero" id="contenido">
        <div className="hero-copy">
          <span className="landing-eyebrow">DESCARGAS EN LA NUBE</span>
          <h1>Tus videos listos para editar. <span>Sin instalar nada.</span></h1>
          <p>
            Pegá un enlace, elegí video o audio y PacheVideo prepara el archivo en nuestros servidores.
            Funciona desde el celular y la computadora.
          </p>
          <div className="hero-actions">
            <Link className="landing-primary" href="/app?auth=signup#cuenta" prefetch={false}>Crear cuenta gratis <ArrowIcon /></Link>
            <a className="landing-secondary" href="#como-funciona">Ver cómo funciona</a>
          </div>
          <div className="hero-proof" aria-label="Beneficios principales">
            <span><CheckIcon /> MP3 hasta 320 kbps</span>
            <span><CheckIcon /> 5 videos gratis hasta 1080p</span>
            <span><CheckIcon /> Sin tarjeta</span>
          </div>
        </div>

        <div className="product-preview" aria-label="Vista previa de PacheVideo">
          <div className="preview-window-bar">
            <span /><span /><span />
            <small>app.pachevideo.com</small>
          </div>
          <div className="preview-body">
            <div className="preview-mode"><strong>Video</strong><span>Audio</span></div>
            <small>ENLACE DEL CONTENIDO</small>
            <div className="preview-url"><span>https://youtu.be/tu-video</span><b>Pegar</b></div>
            <div className="preview-options">
              <div><small>CALIDAD</small><strong>Full HD · 1080p</strong></div>
              <div><small>FORMATO</small><strong>MP4</strong></div>
            </div>
            <div className="preview-progress">
              <div><span>PROCESANDO EN EL SERVIDOR</span><strong>Preparando tu video…</strong></div>
              <b>72%</b>
            </div>
            <div className="preview-track"><i /></div>
          </div>
          <div className="preview-glow" />
        </div>
      </section>

      <section className="logo-strip" aria-label="Pensado para creadores">
        <span>PARA</span>
        <strong>Editores</strong><i />
        <strong>Creadores</strong><i />
        <strong>Social media</strong><i />
        <strong>Equipos de contenido</strong>
      </section>

      <section className="landing-section how-section" id="como-funciona">
        <div className="landing-section-heading">
          <span>ASÍ DE SIMPLE</span>
          <h2>Del enlace al archivo en tres pasos</h2>
          <p>El procesamiento sucede en la nube. Tu dispositivo queda libre para seguir trabajando.</p>
        </div>
        <div className="steps-grid">
          <article><b>01</b><h3>Pegá el enlace</h3><p>Copiá la URL del contenido que tenés autorización para usar.</p></article>
          <article><b>02</b><h3>Elegí el formato</h3><p>Video MP4 o audio MP3, con la calidad que necesites.</p></article>
          <article><b>03</b><h3>Descargá el resultado</h3><p>Recibí un enlace temporal cuando el archivo esté preparado.</p></article>
        </div>
      </section>

      <section className="landing-section feature-section">
        <div className="feature-grid">
          <article className="feature-main">
            <span>TODO OCURRE EN EL SERVIDOR</span>
            <h2>Potencia de escritorio, desde cualquier pantalla.</h2>
            <p>No necesitás instalar FFmpeg ni mantener una computadora encendida para procesar el archivo.</p>
            <div className="server-visual" aria-hidden="true">
              <i /><i /><i />
              <div><span>URL</span><b>→</b><span>FFmpeg</span><b>→</b><span>MP4</span></div>
            </div>
          </article>
          <article className="feature-card"><span>WEB Y APP DE ESCRITORIO</span><h3>Una misma experiencia</h3><p>Probá desde el navegador y usá la aplicación instalada en Windows o macOS cuando trabajes desde tu computadora.</p></article>
          <article className="feature-card"><span>ARCHIVOS TEMPORALES</span><h3>Menos exposición</h3><p>Los resultados vencen y se eliminan automáticamente del servidor.</p></article>
        </div>
      </section>

      <section className="landing-section pricing-section" id="planes">
        <div className="landing-section-heading">
          <span>PLANES TRANSPARENTES</span>
          <h2>Empezá gratis. Pasate a Pro cuando lo necesites.</h2>
          <p>Registrate sin tarjeta y recibí 5 videos gratis hasta 1080p. Video Pro habilita 2K, 4K, máxima calidad y listas de enlaces.</p>
        </div>
        <div className="landing-plans">
          <article className="landing-plan-card">
            <span className="landing-plan-name">GRATIS</span>
            <div className="landing-price"><strong>$0</strong><span>para siempre</span></div>
            <p>Creá tu cuenta y empezá con cinco descargas de video sin pagar.</p>
            <ul>
              <li><CheckIcon /> MP3 hasta 320 kbps</li>
              <li><CheckIcon /> 5 videos gratis hasta 1080p</li>
              <li><CheckIcon /> Acceso desde cualquier dispositivo</li>
              <li className="plan-muted"><CheckIcon /> Incluye anuncios</li>
            </ul>
            <Link className="plan-button secondary" href="/app?auth=signup#cuenta" prefetch={false}>Crear cuenta gratis</Link>
          </article>

          <article className="landing-plan-card pro">
            <span className="recommended-badge">RECOMENDADO</span>
            <span className="landing-plan-name">VIDEO PRO</span>
            <div className="landing-price"><strong>$9.999,99</strong><span>ARS / mes</span></div>
            <p>Para creadores y equipos que descargan contenido todos los días.</p>
            <ul>
              <li><CheckIcon /> Video en 2K, 4K o máxima calidad</li>
              <li><CheckIcon /> Listas de hasta 20 enlaces</li>
              <li><CheckIcon /> Videos sin cupo mensual</li>
              <li><CheckIcon /> Aplicación para Windows y macOS</li>
              <li><CheckIcon /> Procesamiento prioritario</li>
              <li><CheckIcon /> Sin anuncios</li>
            </ul>
            <Link className="plan-button" href="/app#planes" prefetch={false}>Suscribirme a Video Pro</Link>
            <small>La suscripción mensual activa Video Pro automáticamente cuando el pago queda confirmado.</small>
          </article>
        </div>
      </section>

      <section className="landing-section faq-section" id="preguntas">
        <div className="landing-section-heading align-left">
          <span>PREGUNTAS FRECUENTES</span>
          <h2>Lo importante, sin letra chica.</h2>
        </div>
        <div className="faq-list">
          <details open><summary>¿PacheVideo funciona desde el celular?</summary><p>Sí. El teléfono envía el trabajo y el servidor procesa el archivo. No necesitás instalar FFmpeg.</p></details>
          <details><summary>¿Las descargas de audio son gratis?</summary><p>Sí. El audio no consume créditos, aunque aplicamos límites técnicos para evitar automatizaciones abusivas.</p></details>
          <details><summary>¿Qué incluye la cuenta Gratis?</summary><p>Audio MP3 hasta 320 kbps y 5 videos gratis hasta Full HD 1080p después de registrarte. Video Pro desbloquea 2K, 4K, máxima calidad y listas de hasta 20 enlaces.</p></details>
          <details><summary>¿Qué significa “videos sin cupo mensual”?</summary><p>Pro no usa créditos mensuales. Mantiene límites de concurrencia y una política de uso razonable para proteger el servicio.</p></details>
          <details><summary>¿Puedo descargar cualquier contenido?</summary><p>Solo contenido propio, licenciado o para el que tengas autorización, respetando las reglas de la plataforma de origen.</p></details>
        </div>
      </section>

      <section className="final-cta">
        <span>LISTO PARA PROBAR</span>
        <h2>Tu próximo archivo empieza con un enlace.</h2>
        <p>Creá tu cuenta y recibí 5 videos gratis. No necesitás tarjeta ni instalar nada.</p>
        <Link className="landing-primary" href="/app?auth=signup#cuenta" prefetch={false}>Crear cuenta gratis <ArrowIcon /></Link>
      </section>

      <footer className="landing-footer">
        <Link className="brand" href="/" prefetch={false}>
          <span className="brand-mark">P</span><span>PACHEVIDEO</span>
        </Link>
        <p>Descargá y convertí contenido autorizado desde cualquier dispositivo.</p>
        <span>© 2026 PacheVideo</span>
      </footer>
    </main>
  );
}
