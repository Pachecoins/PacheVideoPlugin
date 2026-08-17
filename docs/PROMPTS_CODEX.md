# Prompts para Codex — Implementación de la auditoría de PacheVideo

**Cómo usar este archivo:** cada bloque es un prompt autónomo. Pegá **uno por sesión**, en orden. No los juntes: pasarle 38 hallazgos de una vez produce parches superficiales que tocan todo y no arreglan nada.

Antes de empezar, asegurate de que `docs/AUDITORIA_PRELANZAMIENTO.md` esté en el repositorio, porque los prompts lo referencian.

---

## Bloque 0 — Hacer a mano, antes de tocar a Codex

No es tarea de Codex. Son 5 minutos y protege todo lo demás.

```bash
cd C:\Users\KATANA\Documents\ChatGPT\PacheVideo

# 1. Verificar que no se cuele nada sensible
git status --short
git check-ignore -v server/data web/node_modules .venv-server dist

# 2. Confirmar a mano que ningún .env con CBU real, códigos Pro o
#    certificados .p12 aparece en la lista de archivos a agregar
git add -A --dry-run | findstr /I ".env .p12 .cer secret token cbu"

# 3. Commit inicial
git add -A
git commit -m "Estado inicial de PacheVideo antes de la auditoría de prelanzamiento"

# 4. Crear el repo REMOTO PRIVADO en GitHub y pushear
git remote add origin git@github.com:<tu-usuario>/PacheVideo.git
git branch -M main
git push -u origin main
```

Después: proteger `main` (requerir PR), y configurar los secretos de Apple del README.

---

# BLOQUE 1 — Seguridad

> Copiá desde acá 👇

Trabajás sobre el repositorio PacheVideo. Es un servicio de descarga y conversión de video/audio: `web/` es el frontend (React sobre vinext/Vite y Cloudflare Workers), `server/` es la API de procesamiento (FastAPI + SQLite + yt-dlp + FFmpeg), `companion/` es la app de escritorio con un helper HTTP local, `deploy/` tiene Docker Compose + Caddy.

Existe una auditoría de prelanzamiento en `docs/AUDITORIA_PRELANZAMIENTO.md`. Leela primero, entera. Esta tarea implementa únicamente el **Bloque 1 (Seguridad)**: los hallazgos **P0-2, P0-1, P1-3 y la parte de código de P1-11**. No toques nada de los otros bloques, aunque veas problemas: están catalogados y tienen su propio turno.

## Tarea 1 — P0-2: cerrar la escritura arbitraria de archivos en el helper local

Archivo principal: `companion/server.py`. Hoy el helper escucha en `127.0.0.1:18765`, responde el preflight con `Access-Control-Allow-Origin: *` (línea ~371), no valida `Origin` ni `Host`, no pide autenticación, y acepta un `outputFolder` absoluto arbitrario (líneas ~441-449). Cualquier página web que el usuario visite puede escribir un archivo en cualquier carpeta, con un nombre que el atacante controla vía el título de su propia página.

Implementá las cinco defensas, no elijas:

1. **Token de sesión.** Al arrancar, generar `secrets.token_urlsafe(32)` y escribirlo en un archivo solo-usuario:
   - Windows: `%LOCALAPPDATA%\PacheVideo\session.token`
   - macOS: `~/Library/Application Support/PacheVideo/session.token`
   - Linux: `~/.local/state/PacheVideo/session.token`

   Permisos `0600` en POSIX. Todo request debe traer `Authorization: Bearer <token>`; comparar con `secrets.compare_digest`. Sin token o con token incorrecto → **401**. Reescribir el token en cada arranque.

2. **Eliminar el CORS comodín.** Sacar `Access-Control-Allow-Origin: *` de `end_headers`. Si el panel UXP de `plugin/` necesita CORS, usar una allowlist explícita de orígenes UXP. Si no, quitar CORS por completo.

3. **Validar el `Host`.** Rechazar con 400 cualquier request cuyo header `Host` no sea exactamente `127.0.0.1:<puerto>` o `localhost:<puerto>`. Esto cierra el rebinding de DNS.

4. **Restringir `outputFolder`.** Aceptar solo rutas que el usuario haya elegido explícitamente en la GUI durante esta sesión (mantener una allowlist en memoria que la GUI puebla). Rechazar siempre: carpetas de arranque de Windows, `Program Files`, `Windows`, `System32`, `/System`, `/Library`, `/usr`, `/etc`, y cualquier ruta con un componente que empiece con punto. Resolver la ruta y verificar que no escape del destino permitido.

5. **Sanear el nombre de salida.** No confiar en `%(title)s`, que viene de la página de origen. Además de `%(title).120B`, aplicar un saneado explícito que elimine `/`, `\`, `:`, `..`, caracteres de control y los reservados de Windows (`<>:"|?*`), y forzar la extensión final según el modo.

Actualizá también los consumidores del helper para que manden el token: `companion/desktop.py` (función `api_json`, línea ~30) y `plugin/index.js` (función `api`, línea ~72). Ambos deben leer el archivo de sesión.

## Tarea 2 — P0-1: sacar la clave Pro hardcodeada

`web/app/pro/page.tsx` línea ~12 pasa `initialProAccessKey="PACHE-PRO-DEMO-2026"` al descargador. Si el operador configura esa clave en `PACHEVIDEO_PRO_ACCESS_KEYS`, cualquiera que visite `/pro` obtiene 4K gratis para siempre. Si no la configura, `/pro` devuelve HTTP 400 en todas las solicitudes y la página no funciona. Verifiqué las dos ramas.

- Eliminar `initialProAccessKey` de `web/app/pro/page.tsx`.
- Convertir `/pro` en una landing de venta, no en un descargador con privilegios.
- En `web/app/components/downloader-app.tsx`, agregar un campo de entrada visible donde el cliente pega **su** código Pro, persistido en `localStorage` bajo su propia clave. Nunca precargado desde el servidor.
- El test `web/tests/rendered-html.test.mjs` (líneas ~44-52) **fija el bug actual** afirmando que `/pro` renderiza "Modo Pro activo". Invertí la afirmación: el HTML de `/pro` **no** debe contener nada que matchee `/PACHE-PRO-|proAccessKey/`.

## Tarea 3 — P1-3: dejar de filtrar errores crudos de yt-dlp al cliente

`server/app/main.py` líneas ~437-438 guardan `str(error)` en `detail` y `error`, y `public_job` (líneas ~183-187) los devuelve tal cual al navegador. Los mensajes de yt-dlp incluyen rutas del sistema de archivos del servidor, URLs internas de CDN y nombres de extractores.

Creá un catálogo cerrado de mensajes en español para el usuario: `fuente_no_soportada`, `contenido_privado`, `contenido_no_disponible`, `limite_de_tamano`, `limite_de_duracion`, `error_temporal`, `error_desconocido`. Mapeá los errores de yt-dlp a ese catálogo reutilizando los marcadores que ya existen en `TRANSIENT_ERROR_MARKERS` y `PERMANENT_ERROR_MARKERS`. El detalle técnico se guarda del lado del servidor asociado al `job_id`, nunca se devuelve.

## Tarea 4 — P1-11 (parte de código): corregir el puerto en la validación SSRF

`server/app/main.py` línea ~207 usa `parsed.port or 443` aunque el esquema sea `http`, lo que puede dar una resolución DNS distinta a la real. Usar el puerto por defecto correcto según el esquema.

La mitigación completa de SSRF es un firewall de egreso a nivel de red — eso no es código y va aparte. No intentes resolverlo en Python.

## Reglas para todo el bloque

- **Agregá tests** para cada corrección. La suite de Python vive en `server/tests/`; la de la web en `web/tests/`.
- Ojo: `python -m unittest discover` **falla hoy** porque falta `server/tests/__init__.py`, y `test_deploy.py` importa `yaml` que no está en ningún `requirements.txt`. Agregá el `__init__.py` y un `requirements-dev.txt` con `pyyaml` para poder correr la suite.
- No refactorices más allá de lo necesario. No reescribas el frontend. No toques el modelo de datos.
- Los 20 tests existentes deben seguir pasando, salvo `rendered-html.test.mjs` que actualizás a propósito en la Tarea 2.
- Un commit por tarea, con mensaje que referencie el ID del hallazgo (ej.: `P0-2: token de sesión y validación de Host en el helper local`).
- Al terminar, listá qué tests agregaste y cómo correrlos.

> Copiá hasta acá 👆

---

# BLOQUE 2 — Estabilidad del servicio

> Copiá desde acá 👇

Trabajás sobre el repositorio PacheVideo (API FastAPI en `server/`, frontend en `web/`, deploy en `deploy/`). Leé `docs/AUDITORIA_PRELANZAMIENTO.md` entera antes de empezar.

Esta tarea implementa el **Bloque 2 (Estabilidad del servicio)**: hallazgos **P0-3, P0-4, P0-6, P1-1, P1-2 y P1-4**. No toques nada fuera de eso.

## Tarea 1 — P0-3: el límite de tasa es global y falsificable

Hay tres bugs superpuestos en `server/app/main.py` línea ~499:

```python
client = request.headers.get("cf-connecting-ip") or request.client.host if request.client else "unknown"
```

- El proxy de Next (`web/app/api/jobs/route.ts` línea ~12) manda la IP en `X-Forwarded-For`, pero el backend lee `cf-connecting-ip`. Resultado: **todos los usuarios comparten una sola cubeta de 8 req/min**. Lo verifiqué: con el límite en 3, el cuarto usuario recibió 429.
- El header es falsificable si el API es alcanzable directamente. Verifiqué: 40 requests con `cf-connecting-ip` falso → 40 aceptadas, límite evadido por completo.
- La precedencia de Python evalúa `(A or B) if C else D`, así que cuando `request.client` es `None` el header se ignora y todo cae en la constante `"unknown"`.

Implementá:

1. Una **única** variable `PACHEVIDEO_TRUSTED_CLIENT_HEADER` (default `x-forwarded-for`). El backend lee solo esa. Alineá `web/app/api/jobs/route.ts` para que envíe exactamente ese header.
2. Extracción con paréntesis explícitos y validación del formato de IP; primera entrada de la lista separada por comas; fallback a `request.client.host`.
3. **Confiar en el header solo si la conexión viene del proxy.** Nueva variable `PACHEVIDEO_TRUSTED_PROXIES` con una lista de IPs/CIDRs. Si `request.client.host` no está en esa lista, ignorar el header y usar la IP de la conexión. Sin esto el bypass sigue abierto.
4. Un token interno compartido `PACHEVIDEO_INTERNAL_TOKEN` entre `web/` y `server/`, verificado en un middleware, para que el API rechace tráfico que no venga del proxy.
5. Subir el default de `PACHEVIDEO_RATE_LIMIT_PER_MINUTE` a 25 una vez que la cubeta sea por IP real.

Agregá las variables nuevas a `deploy/docker-compose.yml`, `deploy/.env.example` y `web/.env.example`.

## Tarea 2 — P0-4: el limpiador borra trabajos que todavía se están descargando

En `server/app/main.py`, `MAX_DURATION_SECONDS` es 10800 (3 h) y `JOB_TTL_SECONDS` es 3600 (1 h), y `cleanup_expired` (líneas ~442-449) borra **sin mirar el estado**. Verifiqué que un trabajo en `downloading` con TTL vencido queda borrado de la base y su carpeta eliminada **mientras yt-dlp escribe adentro**; el usuario ve 404 con la barra al 40%.

1. El limpiador solo borra trabajos con `status IN ('complete','error')`.
2. Separar dos relojes:
   - `processing_deadline = created_at + MAX_PROCESSING_SECONDS` — si se supera, marcar el trabajo `error` con mensaje claro y recién ahí limpiar.
   - `expires_at` **recalculado al completar**, no en la creación: `completed_at + DOWNLOAD_WINDOW_SECONDS` (default 1800 s).
   Hoy `expires_at` se fija en la creación (línea ~533), así que un video que tardó 55 minutos deja 5 minutos para bajar 2 GB.
3. Barrido separado para zombis: trabajos en `queued`/`downloading`/`processing`/`retrying` más viejos que el deadline de procesamiento.
4. Antes de borrar una carpeta, verificar que ningún worker la tenga tomada (un `threading.Lock` por `job_id` o un archivo centinela).
5. Migración de esquema: agregar `completed_at`. Seguí el patrón de migraciones que ya existe en `initialize_database` (líneas ~147-157).

## Tarea 3 — P0-6: cola y disco sin límite

`ThreadPoolExecutor` (línea ~91) tiene cola **ilimitada** y nada consulta el disco libre. Un usuario con 20 URLs de 3 horas llena el volumen. Además el chequeo de tamaño (línea ~419) ocurre **después** de escribir el archivo completo, y `max_filesize` de yt-dlp no cubre descargas fragmentadas ni el archivo fusionado.

1. Cola acotada (`queue.Queue(maxsize=N)` con workers propios, o equivalente). Cuando esté llena, devolver **HTTP 503 con `Retry-After`**, no encolar.
2. Límite de trabajos activos por IP/cuenta: 1 concurrente en Gratis, 3 en Pro. Esto además le da sustancia real al "procesamiento prioritario" que se vende.
3. Verificar disco antes de aceptar: `shutil.disk_usage(DOWNLOAD_DIR).free` contra `MAX_FILE_BYTES * (pendientes + 1) * margen`. Si no alcanza → 503.
4. **Cortar durante la descarga, no después**: usar `progress_hook` para abortar en cuanto `downloaded_bytes` supere `MAX_FILE_BYTES` (lanzar una excepción desde el hook detiene a yt-dlp).
5. Bajar el default de `MAX_DURATION_SECONDS` a 3600.
6. Al arrancar, reencolar o marcar `error` los trabajos que quedaron `queued` de un reinicio anterior. Hoy quedan colgados para siempre.

## Tarea 4 — P1-1 y P1-2: fugas y contención

- `rate_windows` (línea ~92) es un `defaultdict` que nunca se purga. Verifiqué: 5000 IPs distintas dejan 5000 claves permanentes. Purgar las ventanas vacías dentro de `consume_rate_limit` o usar una caché acotada con TTL.
- `PRAGMA journal_mode=WAL` y `PRAGMA synchronous=NORMAL` en `initialize_database`. Hoy el journal mode es `delete`, así que lectores y escritores se bloquean, y el frontend hace polling cada 900 ms.
- `progress_hook` (líneas ~320-328) llama a `update_job` en **cada** callback, y `update_job` (líneas ~160-166) abre una conexión SQLite nueva cada vez. Medí 500 llamadas en 0,48 s; yt-dlp dispara el hook miles de veces por descarga. Throttlear a máximo una escritura por segundo o cada 2 % de avance, y reutilizar una conexión por hilo con `threading.local`.

## Tarea 5 — P1-4: el servidor no tiene logging estructurado

`server/app/main.py` no configura logging y **no pasa `logger` a yt-dlp**, a diferencia de `companion/server.py` que sí lo hace (líneas ~82-93). Verifiqué que yt-dlp escribe `ERROR: ...` a stderr a pesar de `quiet: True`, filtrando URLs de usuarios sin control.

- Logging JSON estructurado con `job_id` y `request_id`.
- Pasar un logger propio a yt-dlp para capturar su salida.
- Exponer métricas Prometheus: trabajos por estado, duración, tasa de error por extractor, profundidad de cola, disco libre.
- Dejar preparado el gancho para Sentry vía variable de entorno.

## Reglas para todo el bloque

- Agregá tests para cada corrección, especialmente: la cubeta de tasa por IP real, el rechazo de headers falsificados desde fuera de la allowlist de proxies, y que un trabajo activo con TTL vencido **no** sea borrado.
- Los tests existentes deben seguir pasando.
- Documentá cada variable de entorno nueva en `deploy/.env.example` y en el README.
- Un commit por tarea, referenciando el ID del hallazgo.

> Copiá hasta acá 👆

---

# BLOQUE 3 — Resiliencia de yt-dlp

> Copiá desde acá 👇

Trabajás sobre el repositorio PacheVideo. Leé `docs/AUDITORIA_PRELANZAMIENTO.md` entera antes de empezar. Esta tarea implementa el **Bloque 3**: hallazgos **P0-8, P1-9 y P1-10**.

Contexto del problema: PacheVideo depende de yt-dlp, y las plataformas de origen cambian sus formatos cada pocas semanas. `server/requirements.txt` pinea `yt-dlp==2026.7.4` dentro de una imagen Docker inmutable, así que el producto **deja de funcionar solo** en 2-6 semanas sin que nadie toque nada. Con suscripciones mensuales activas eso es una ola de reembolsos. Peor: `/api/health` reporta la versión pero nunca prueba una extracción real, así que el healthcheck da verde con el servicio totalmente roto.

## Tarea 1 — P0-8a: canario de extracción

Agregá un chequeo periódico (cada 15 minutos, en el mismo patrón de hilo que usa `cleanup_expired`) que corra `extract_info(download=False)` contra 2-3 URLs estables configurables por variable de entorno. Exponer el resultado en `/api/health` como `extractorOk`, `extractorCheckedAt` y `extractorFailures`. El healthcheck de Docker debe fallar si el canario lleva más de N ciclos en rojo. El chequeo nunca debe bloquear los workers de descarga.

## Tarea 2 — P0-8b: actualización sin redeploy

Implementá una de las dos, la que consideres más robusta para este stack, y documentá la decisión:
- un workflow de GitHub Actions que reconstruya y publique la imagen cada noche con la última `yt-dlp`, con capacidad de rollback a un tag anterior, o
- yt-dlp en un volumen escribible actualizado por un job programado, con verificación posterior por el canario y rollback automático si el canario se pone rojo.

## Tarea 3 — P1-9: la caché de yt-dlp no puede escribir

`deploy/docker-compose.yml` línea ~19 fija `read_only: true` con `tmpfs` solo en `/tmp`. El home de `pachevideo` no es escribible, así que `~/.cache/yt-dlp` falla — y eso desactiva justo los mecanismos que ayudan a yt-dlp a recuperarse de cambios en el origen.

`ENV XDG_CACHE_HOME=/tmp/cache` en `server/Dockerfile`, o `"cachedir"` explícito en las opciones. Verificá además que los 512 MB de `tmpfs` en `/tmp` alcanzan para el trabajo temporal de FFmpeg con archivos grandes; si no, subilo y documentalo.

## Tarea 4 — P1-10: el modo audio puede entregar un archivo que no es MP3

`server/app/main.py` líneas ~281-291: si la conversión con `FFmpegExtractAudio` falla pero el `.webm` original quedó en disco, la rama de respaldo de `locate_output` toma "el archivo más reciente que no termine en `.part`" y lo sirve. El usuario pidió MP3 320 kbps y recibe un `.webm` que no le abre en el reproductor.

Validar que la extensión de salida coincida con la solicitada. Si no coincide, tratarlo como error y reintentar. Test que lo cubra.

## Tarea 5 — Runbook

Escribí `docs/RUNBOOK_INCIDENTES.md`: qué hacer cuando la extracción se cae. Banner de estado en la web, pausar altas nuevas, actualizar yt-dlp, verificar con el canario, comunicar a los suscriptores. Incluí los comandos concretos.

## Reglas

- Tests para el canario (con la extracción mockeada) y para la validación de extensión.
- Un commit por tarea, referenciando el ID del hallazgo.

> Copiá hasta acá 👆

---

# BLOQUE 4 — Modelo comercial

> Copiá desde acá 👇

Trabajás sobre el repositorio PacheVideo. Leé `docs/AUDITORIA_PRELANZAMIENTO.md` **y** `docs/LANZAMIENTO_WEB.md` antes de empezar. Este es el bloque más grande: **P0-5, P1-12 y P1-8**.

El problema central: **el plan gratuito no existe del lado del servidor**. `server/app/main.py` líneas ~253-256 limitan la **calidad** pero nunca la **cantidad**. El límite de "1 video de prueba" vive solo en `localStorage` (`web/app/components/downloader-app.tsx` líneas ~46 y ~73). Verifiqué: 10 solicitudes de video gratis desde 10 IPs distintas → **10 aceptadas**. El audio no tiene ninguna cuota, ni cliente ni servidor. Sin cuentas tampoco hay forma de suspender a un abusador, emitir un reembolso ni responder un pedido legal.

`docs/LANZAMIENTO_WEB.md` ya tiene el diseño correcto (tablas `users`, `subscriptions`, `credit_ledger`, `jobs`, `webhook_events`). **Seguí ese diseño**, no inventes uno nuevo.

## Tarea 1 — P1-12: migrar a PostgreSQL primero

Hacé esto **antes** del libro mayor de créditos. Un ledger financiero sobre SQLite en un volumen local sin backups no es aceptable.

- Migrar de SQLite a PostgreSQL. Mantené la capa de acceso a datos aislada para no esparcir SQL por todo `main.py`.
- Cola durable: tabla de trabajos con locking (`FOR UPDATE SKIP LOCKED`) en lugar de la cola en memoria. Hoy un reinicio pierde en silencio todo lo pendiente.
- Actualizar `deploy/docker-compose.yml` con el servicio de base y sus backups.
- Documentar el procedimiento de restauración y **probarlo**, no solo configurarlo.

## Tarea 2 — P0-5: cuentas y cuotas del lado del servidor

1. **Cuentas con email verificado.** Magic link alcanza; no hace falta contraseña. Sesión con cookie `HttpOnly` + `Secure` + `SameSite`.
2. **Cuota impuesta en el servidor, en la misma transacción que crea el trabajo:**
   - reservar el crédito **antes** de encolar,
   - devolverlo si el trabajo termina en `error` o se cancela,
   - consumirlo definitivamente al completar.
3. **`credit_ledger` como libro mayor append-only**, nunca un contador mutable. Es necesario para auditar disputas de pago. Movimientos idempotentes.
4. **Cuota para audio también** — hoy es el vector de abuso más barato.
5. **Cuota anónima de contención** como paso intermedio mientras se construye lo anterior: límite duro por IP en la base de datos (no en memoria), 3 videos por 24 h. No es antifraude serio, pero es infinitamente mejor que `localStorage`.
6. Ligar el desbloqueo Pro a la sesión autenticada, reemplazando los códigos de `PACHEVIDEO_PRO_ACCESS_KEYS`. Mantené los códigos como camino de compatibilidad para la beta manual en curso, pero atados a una cuenta.

## Tarea 3 — P1-8: textos legales y registro de aceptación

No existen `/terminos`, `/privacidad` ni `/dmca`. Peor: el test `web/tests/rendered-html.test.mjs` línea ~38 afirma `assert.doesNotMatch(html, /Confirmo que el contenido es mío|type="checkbox"/i)` — la aceptación de términos **se quitó a propósito y el test impide que vuelva**. Al mismo tiempo `scripts/smoke-webapp.py` línea ~29 sigue enviando `acceptedTerms: True`, un campo que el modelo `CreateJob` ni define.

- Crear las páginas `/terminos`, `/privacidad` y `/dmca` con contenido real (dejá `TODO` marcados donde haga falta revisión legal humana, pero la estructura completa).
- Reinstaurar la aceptación explícita en el primer uso y **registrarla**: timestamp + versión de los términos + cuenta.
- Invertir la afirmación del test para que **exija** la aceptación.
- Alinear `scripts/smoke-webapp.py` con el modelo real.

## Reglas

- Este bloque toca dinero. Cada movimiento del ledger necesita un test, incluyendo los caminos de error: trabajo que falla después de reservar, doble webhook de pago, cancelación a mitad de descarga.
- Migraciones reversibles y probadas contra datos existentes.
- No rompas el flujo actual de códigos Pro hasta que el reemplazo funcione.
- Un commit por tarea.

> Copiá hasta acá 👆

---

# BLOQUE 5 — Producto y entrega

> Copiá desde acá 👇

Trabajás sobre el repositorio PacheVideo. Leé `docs/AUDITORIA_PRELANZAMIENTO.md` entera. Esta tarea implementa el **Bloque 5**: hallazgos **P1-5, P1-6, P1-7, P1-13, P1-14, P1-15, P1-16 y P1-17**.

## Tarea 1 — P1-5: dos bucles de polling simultáneos

`web/app/components/downloader-app.tsx` líneas ~101-127: `startDownload()` no hace `clearTimeout(pollTimer.current)` antes de arrancar. Si el usuario pulsa "Reintentar ahora" (línea ~285) o inicia otra descarga con una en curso, quedan **dos bucles activos** pisándose el `setJob`: se ve como progreso que retrocede o un trabajo "completo" que vuelve a "descargando".

Limpiar el timer al inicio de `startDownload()`, y usar un `AbortController` más un token de generación para descartar respuestas de bucles viejos.

## Tarea 2 — P1-6: la PWA no cumple los requisitos de instalación

- `web/public/manifest.webmanifest` declara **un solo icono de 165×165**. Chrome y Android exigen 192×192 y 512×512 para ofrecer "Agregar a inicio". Generá los iconos faltantes, incluido uno `maskable`, y declaralos todos.
- `web/public/sw.js` es un stub de dos líneas sin handler `fetch`. Escribí un service worker real: app shell cacheado, `no-store` para `/api/*`, estrategia de actualización.
- `server/tests/test_deploy.py` líneas ~22-32 **cristalizan el bug**: afirman que el manifiesto coincide con las dimensiones de `logo.png`. Reescribí el test para que exija los tamaños requeridos por la especificación PWA.

## Tarea 3 — P1-7: unificar el camino de descarga

Hoy hay **dos caminos distintos** según la configuración, y el que se ejercita en desarrollo no es el de producción:
- `web/app/api/jobs/[id]/download/route.ts` transmite el archivo completo a través del Worker de Cloudflare — con archivos de hasta 2 GB eso consume CPU y egreso del Worker en cada descarga.
- `web/app/api/jobs/[id]/route.ts` línea ~24 deriva al usuario **directo al backend** cuando `PACHEVIDEO_PUBLIC_BASE_URL` es HTTPS, salteándose el proxy.

Elegí **un solo camino**. Lo recomendable es almacenamiento de objetos (R2/S3) con URLs prefirmadas de vida corta: saca el tráfico pesado del Worker y del backend, sobrevive a reinicios y es el prerrequisito para escalar de 1 servidor a N. Documentá la decisión y actualizá `docs/ESTIMACION_INFRAESTRUCTURA.md`, que hoy no contempla el costo del proxy por Worker.

## Tarea 4 — P1-13: CI que corra los tests

`.github/workflows/release-macos.yml` es el único workflow y solo construye instaladores de macOS. **Nada** corre los tests de Python, el `npm run test` de la web ni el lint. No hay CI de Windows.

Además la suite de Python no se puede descubrir: falta `server/tests/__init__.py` (`python -m unittest discover` falla con `Start directory is not importable`) y `test_deploy.py` importa `yaml`, que no está en ningún `requirements.txt`.

- Agregar `server/tests/__init__.py` y `requirements-dev.txt` con `pyyaml`.
- Documentar el comando de test en el README.
- Crear `.github/workflows/ci.yml` que corra tests de Python, tests de la web y ESLint en cada PR. Obligatorio para mergear.
- Agregar el workflow de build de Windows que falta (hoy `scripts/build-windows-installer.ps1` solo corre a mano).

## Tarea 5 — P1-14 a P1-16: robustez del helper de escritorio

- **P1-14:** `companion/server.py` líneas ~476-479 salen con código 0 si el puerto está ocupado, y la GUI muestra "Helper desconectado" sin explicar por qué. Salir con código distinto de cero, log accionable, y probar puertos alternativos publicando el elegido en el archivo de sesión que lee el cliente.
- **P1-15:** el diccionario `jobs` (línea ~141) nunca se purga y el helper arranca con Windows, así que corre semanas. Purgar trabajos terminados a los 30 minutos, con tope duro de entradas.
- **P1-16:** las carpetas `.pachevideo-<id>` (línea ~230) se crean **dentro de la carpeta de descargas del usuario** y quedan huérfanas si el helper se mata. Usar el directorio temporal del sistema y mover el resultado final; barrer carpetas viejas al arrancar.

## Tarea 6 — P1-17: cancelación de trabajos

Ni la web ni el escritorio permiten cancelar. Un usuario que pegó la URL equivocada de un video de 3 horas ocupa uno de los dos workers hasta el final.

`DELETE /api/jobs/{id}` con token: marca el trabajo cancelado, aborta yt-dlp desde el `progress_hook`, limpia la carpeta y devuelve el crédito si el Bloque 4 ya está implementado. Botón "Cancelar" en la tarjeta de progreso de la web y en la GUI de escritorio.

## Reglas

- Tests para cada corrección. Verificá la instalación de la PWA en iOS Safari y Android Chrome si tenés forma de hacerlo; si no, dejá documentado el procedimiento manual.
- Un commit por tarea, referenciando el ID del hallazgo.

> Copiá hasta acá 👆

---

# Prompt de verificación final

Usalo cuando los cinco bloques estén hechos, en una sesión limpia.

> Copiá desde acá 👇

Trabajás sobre el repositorio PacheVideo. Leé `docs/AUDITORIA_PRELANZAMIENTO.md` entera, con atención especial a la sección **"Pruebas mínimas que deben pasar antes de lanzar"** (30 pruebas, agrupadas en Seguridad, Límites y cuotas, Ciclo de vida de los trabajos, Funcionalidad y Plataforma).

Tu tarea es **verificar**, no implementar. Trabajá en modo solo lectura salvo para agregar tests que falten.

1. Para cada una de las 30 pruebas, determiná si existe un test automatizado que la cubra. Armá una tabla: número de prueba, estado (`cubierta` / `parcial` / `ausente`), y el archivo:línea del test cuando exista.
2. Para las que estén ausentes o parciales, escribí el test.
3. Corré la suite completa (Python y web) y reportá los resultados.
4. Para cada hallazgo P0 y P1 de la auditoría, verificá que la corrección esté realmente aplicada leyendo el código. No confíes en el mensaje del commit. Reportá cualquiera que siga abierto o que se haya arreglado solo a medias.
5. Cerrá con un veredicto explícito: **listo para lanzar** o **no listo**, con la lista de lo que falta.

No arregles los defectos que encuentres en este pase. Reportalos.

> Copiá hasta acá 👆
