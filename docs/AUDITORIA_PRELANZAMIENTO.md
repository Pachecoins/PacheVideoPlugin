# Auditoría de prelanzamiento — PacheVideo

**Fecha:** 17 de agosto de 2026
**Alcance:** `web/`, `server/`, `companion/`, `plugin/`, `packaging/`, `deploy/`, `scripts/`, `docs/`, tests
**Método:** lectura completa del código + ejecución de la suite de tests + reproducción de defectos con FastAPI TestClient y arranque real del helper local
**Modo:** solo lectura. No se modificó ningún archivo del proyecto.

---

## Veredicto

**No lanzar todavía.** El producto funciona en el camino feliz y la ingeniería es más prolija que la de un MVP típico: hay reintentos con clasificación de errores, backoff, validación de SSRF, tokens firmados, limpieza automática y contenedor endurecido. Eso es real y hay que reconocerlo.

Pero hay **8 defectos P0** que, en conjunto, significan tres cosas concretas:

1. **El modelo de negocio no está aplicado en ningún lado.** El límite de "1 video gratis" vive únicamente en `localStorage`. El servidor acepta descargas ilimitadas de cualquiera. Cobrar $9.999,99 ARS/mes por algo que se obtiene gratis borrando datos del navegador no es viable.
2. **El servicio se cae solo con 4 usuarios simultáneos** por un bug de una sola línea en la lectura de la IP del cliente.
3. **El instalador de escritorio contiene una vulnerabilidad de escritura arbitraria de archivos** explotable desde cualquier página web que el usuario visite. Firmar y distribuir ese binario tal como está es un problema serio.

Ninguno de los tres es difícil de arreglar. La estimación es **6 a 10 días de trabajo enfocado** para llegar a un lanzamiento defendible, más lo que tome el sistema de cuentas.

### Resumen de hallazgos

| Prioridad | Cantidad | Significado |
|---|---|---|
| **P0** | 8 | Bloquean el lanzamiento. Pérdida de ingresos, caída del servicio o riesgo de seguridad. |
| **P1** | 17 | Arreglar antes de abrir el registro público. Degradan la experiencia o el costo. |
| **P2** | 9 | Deuda técnica que conviene saldar en las primeras semanas. |
| **P3** | 4 | Prolijidad. |

---

# P0 — Bloqueantes de lanzamiento

## P0-1 · La página `/pro` publica una clave Pro hardcodeada y además está rota

**Evidencia**

```tsx
// web/app/pro/page.tsx:10-15
<DownloaderApp
  initialProAccessKey="PACHE-PRO-DEMO-2026"
  proPreview
/>
```

**Impacto (doble, y las dos ramas son malas):**

- **Si el operador configura `PACHEVIDEO_PRO_ACCESS_KEYS=PACHE-PRO-DEMO-2026`:** cualquiera que entre a `pachevideo.com/pro` obtiene 2K, 4K, calidad máxima, descarga concurrente por fragmentos y sin límite de velocidad, gratis y para siempre. La clave está en el HTML servido; no hace falta ni abrir DevTools.
- **Si no lo configura (que es el default, `PRO_ACCESS_KEYS` arranca vacío):** *toda* solicitud desde `/pro` devuelve **HTTP 400 "El código de Video Pro no es válido"**. La página que el marketing usa para vender el plan pago no funciona en absoluto.

**Reproducción (verificada):**

```
POST /api/jobs {"url":"...","quality":"1440","proAccessKey":"PACHE-PRO-DEMO-2026"}
→ HTTP 400: {'detail': 'El código de Video Pro no es válido'}
```

Agravante: el test `web/tests/rendered-html.test.mjs:44-52` **fija este comportamiento** (`assert.match(html, /Modo Pro activo/)`), así que un arreglo va a romper el test y hay que actualizarlo también.

**Corrección**

1. Eliminar `initialProAccessKey` de `web/app/pro/page.tsx`. La página `/pro` debe ser una **landing de venta**, no un descargador con privilegios.
2. La activación Pro debe entrar por una sesión autenticada (ver P0-5), no por una constante en el código fuente.
3. Mientras dure la beta manual con códigos: agregar un campo de entrada visible donde el cliente pega *su* código, y persistirlo en `localStorage` bajo su propia clave. Nunca precargarlo desde el servidor.
4. Actualizar `rendered-html.test.mjs` para que afirme lo contrario: que `/pro` **no** contiene ninguna cadena que matchee `/PACHE-PRO-|proAccessKey/`.

---

## P0-2 · El helper de escritorio permite escritura arbitraria de archivos desde cualquier sitio web

**Evidencia**

```python
# companion/server.py:370-375
def end_headers(self) -> None:
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
```

```python
# companion/server.py:441-449
requested_folder = str(payload.get("outputFolder") or "").strip()
output_folder = Path(requested_folder).expanduser() if requested_folder else OUTPUT_FOLDER
if not output_folder.is_absolute():
    raise ValueError("La carpeta de destino debe usar una ruta absoluta")
output_folder = output_folder.resolve()
output_folder.mkdir(parents=True, exist_ok=True)
```

**Impacto — este es el hallazgo más grave del informe.**

El helper escucha en `127.0.0.1:18765`, responde el preflight CORS con `Access-Control-Allow-Origin: *`, no valida `Origin`, no valida `Host` (por lo tanto es vulnerable también a DNS rebinding), y **no tiene ningún token de autenticación**. Cualquier página web que el usuario tenga abierta puede:

1. Detectar que PacheVideo está instalado (`GET /health` devuelve versión, carpeta de descargas y ruta del log — huella digital perfecta).
2. Hacer `POST /downloads` con un `outputFolder` absoluto **arbitrario** y una `url` que el atacante controla.
3. El nombre del archivo escrito sale de `%(title)s` — es decir, del **título de la página del atacante** (`companion/server.py:274`).

El atacante controla destino y nombre. En Windows eso incluye `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`, lo que convierte esto en persistencia y ejecución de código en el próximo login. También sirve para plantar archivos incriminatorios o llenar el disco.

**Reproducción (verificada con el helper real corriendo):**

```
OPTIONS /health  → 204 | Access-Control-Allow-Origin: *
POST /downloads {"url":"https://…","outputFolder":"<ruta arbitraria>"}
  con Origin: https://sitio-malicioso.example
→ 202 {"id": "8db0593aa64f40c09d84a18541e57930"}
→ carpeta creada por el helper en la ruta arbitraria: True
```

**Corrección (las cinco, no elegir)**

1. **Token de sesión.** Al arrancar, el helper genera `secrets.token_urlsafe(32)` y lo escribe en un archivo solo-usuario (`%LOCALAPPDATA%\PacheVideo\session.token` / `~/Library/Application Support/PacheVideo/session.token`, permisos `0600`). Todo request debe traer `Authorization: Bearer <token>`; comparar con `secrets.compare_digest`. La app de escritorio y el panel UXP leen ese archivo. Una página web no puede.
2. **Eliminar el CORS comodín.** Reemplazar `Access-Control-Allow-Origin: *` por una allowlist explícita de orígenes UXP, o quitar CORS por completo si solo consumen clientes locales.
3. **Validar el `Host`.** Rechazar cualquier request cuyo `Host` no sea `127.0.0.1:18765` o `localhost:18765`. Esto cierra el DNS rebinding.
4. **Restringir `outputFolder`.** Aceptar únicamente rutas dentro de una allowlist que el *usuario* haya elegido en la GUI durante esta sesión. Rechazar rutas del sistema, carpetas de arranque, `Program Files`, `/System`, `/Library/LaunchAgents`, y cualquier ruta con un componente oculto.
5. **Sanear el nombre de salida.** No confiar en `%(title)s`. Aplicar `outtmpl` con `%(title).120B` más un saneado explícito que elimine separadores de ruta, `:`, `..` y caracteres reservados de Windows, y forzar la extensión final.

> **No firmar ni publicar el instalador hasta que esto esté corregido.** Un binario firmado con esta falla es peor que uno sin firmar: la firma le da confianza al ataque.

---

## P0-3 · El límite de tasa es global: 4 usuarios simultáneos tiran el servicio

**Evidencia**

```python
# server/app/main.py:499
client = request.headers.get("cf-connecting-ip") or request.client.host if request.client else "unknown"
```

```ts
// web/app/api/jobs/route.ts:12
"X-Forwarded-For": request.headers.get("cf-connecting-ip") || "unknown",
```

**Impacto**

Hay dos bugs superpuestos:

**(a) Cubeta compartida.** El proxy de Next reenvía la IP en `X-Forwarded-For`, pero el backend **nunca lee ese header** — lee `cf-connecting-ip`, que el proxy no setea. Resultado: todas las solicitudes llegan con el mismo `request.client.host` (la IP del proxy) y comparten **una sola cubeta de 8 requests por minuto para todo el planeta**. Con el default de `PACHEVIDEO_RATE_LIMIT_PER_MINUTE=8`, el noveno usuario del minuto recibe 429. Esto es una autodenegación de servicio garantizada el día del lanzamiento.

**(b) El header es falsificable.** Si el API es alcanzable directamente (y tiene que serlo: `PACHEVIDEO_PUBLIC_BASE_URL` genera enlaces de descarga directos, `main.py:191-193`), cualquiera puede mandar `cf-connecting-ip: <aleatorio>` y **saltarse el límite por completo**.

**(c) Precedencia rota.** `A or B if C else D` en Python se evalúa como `(A or B) if C else D`. Cuando `request.client` es `None` (habitual detrás de algunos proxies ASGI), el header se ignora aunque esté presente y todo cae en la constante `"unknown"` — otra cubeta única compartida.

**Reproducción (verificada, con `RATE_LIMIT_PER_MINUTE=3`):**

```
5 usuarios distintos vía X-Forwarded-For → 202, 202, 202, 429, 429   ← se pisan entre sí
40 requests con cf-connecting-ip falsificado → 40 aceptadas, 0 bloqueadas
```

**Corrección**

1. Definir una **única** variable de confianza, p. ej. `PACHEVIDEO_TRUSTED_CLIENT_HEADER` (default `x-forwarded-for`), y leer solo esa. Alinear `web/app/api/jobs/route.ts` para que envíe exactamente ese header.
2. Extraer la IP con paréntesis explícitos y validar el formato:
   ```python
   def client_ip(request: Request) -> str:
       raw = request.headers.get(TRUSTED_CLIENT_HEADER, "")
       candidate = raw.split(",")[0].strip()
       try:
           return str(ipaddress.ip_address(candidate))
       except ValueError:
           return request.client.host if request.client else "unknown"
   ```
3. **Confiar en el header solo si la conexión viene del proxy.** Comparar `request.client.host` contra una allowlist de IPs de proxy (`PACHEVIDEO_TRUSTED_PROXIES`). Si no coincide, usar la IP de la conexión e ignorar el header. Sin esto, (b) sigue abierto.
4. Bloquear el acceso directo al API desde fuera del proxy: `PACHEVIDEO_INTERNAL_TOKEN` compartido entre `web/` y `server/`, verificado en un middleware, o Cloudflare Access / mTLS.
5. Subir `RATE_LIMIT_PER_MINUTE` a un valor sensato por IP real (20-30) una vez que la cubeta sea correcta.

---

## P0-4 · El limpiador borra trabajos que todavía se están descargando

**Evidencia**

```python
# server/app/main.py:44-46
MAX_DURATION_SECONDS = int(os.getenv("PACHEVIDEO_MAX_DURATION_SECONDS", "10800"))  # 3 horas
JOB_TTL_SECONDS      = int(os.getenv("PACHEVIDEO_JOB_TTL_SECONDS", "3600"))        # 1 hora
```

```python
# server/app/main.py:442-449
def cleanup_expired() -> None:
    while not stop_cleanup.wait(60):
        now = time.time()
        with database() as connection:
            rows = connection.execute("SELECT id FROM jobs WHERE expires_at < ?", (now,)).fetchall()
            connection.execute("DELETE FROM jobs WHERE expires_at < ?", (now,))
        for row in rows:
            shutil.rmtree(DOWNLOAD_DIR / row["id"], ignore_errors=True)
```

**Impacto**

`expires_at` se fija en la **creación** (`main.py:533`) y el limpiador borra **sin mirar el estado**. Como la duración máxima permitida (3 h) triplica el TTL (1 h), un video largo tiene la expiración garantizada antes de terminar:

- La fila desaparece de la base → los `update_job()` posteriores actualizan 0 filas en silencio → el frontend recibe **404 a mitad de la descarga**.
- `shutil.rmtree` borra la carpeta **mientras yt-dlp/FFmpeg escriben adentro** → el proceso muere con un error de I/O incomprensible, y los descriptores abiertos dejan basura en disco.
- Efecto secundario relacionado: **`expires_at` tampoco se extiende al completar**. Un usuario cuyo video tardó 55 minutos tiene 5 minutos para bajar 2 GB por datos móviles antes de que el archivo se evapore.

**Reproducción (verificada):**

```
job 'activo', status='downloading', expires_at vencido
→ ciclo del limpiador: filas borradas ['activo']
→ carpeta de trabajo aún existe? False
→ get_job('activo') → None       # el usuario ve 404 con la barra en 40%
```

**Corrección**

1. **Nunca borrar trabajos activos.** Cambiar la consulta a:
   ```sql
   SELECT id FROM jobs
   WHERE expires_at < ? AND status IN ('complete','error')
   ```
2. **Sembrar el TTL con margen sobre la duración máxima**, o mejor: separar dos relojes.
   - `processing_deadline = created_at + MAX_PROCESSING_SECONDS` (matar el trabajo si lo supera).
   - `expires_at = completed_at + DOWNLOAD_WINDOW_SECONDS` (**recalculado al completar**, no en la creación).
3. Fijar `DOWNLOAD_WINDOW_SECONDS` en 1800-3600 desde que el archivo está listo, no desde que se encoló.
4. Barrido separado para trabajos zombi: `status IN ('queued','downloading','processing','retrying') AND created_at < now - MAX_PROCESSING_SECONDS` → marcar `error` con un mensaje claro y *después* limpiar la carpeta.
5. Al borrar carpetas, verificar que ningún worker las tenga tomadas (un `threading.Lock` por `job_id`, o un archivo centinela).

---

## P0-5 · El plan gratuito no existe del lado del servidor

**Evidencia**

```tsx
// web/app/components/downloader-app.tsx:46
setFreeVideoUsed(localStorage.getItem("pachevideo-free-video-used") === "1");
// :73
localStorage.setItem("pachevideo-free-video-used", "1");
// :103
if (mode === "video" && !proAccessKey.trim() && freeVideoUsed) { … }
```

```python
# server/app/main.py:253-256 — lo único que el servidor impone
def enforce_plan_limits(mode: str, quality: str, plan: str) -> None:
    if mode == "video" and quality not in FREE_VIDEO_QUALITIES and plan != "pro":
        raise ValueError("2K, 4K y calidad máxima están disponibles con Video Pro")
```

**Impacto**

El servidor limita **la calidad**, nunca **la cantidad**. No hay usuarios, ni sesiones, ni cuotas, ni contadores persistentes. El límite comercial de "1 video de prueba" se aplica exclusivamente con una clave de `localStorage`, que se evade con: modo incógnito, otro navegador, "borrar datos del sitio", DevTools, o un `curl` directo al API.

El audio no tiene **ningún** límite de cuota — ni cliente ni servidor. Es una descarga y transcodificación ilimitada, gratis, para cualquiera.

Sin autenticación tampoco hay forma de suspender a un abusador, ni de correlacionar consumo con ingresos, ni de emitir un reembolso, ni de responder un pedido legal. `docs/MVP_PRODUCTO.md` ya lo dice explícitamente ("sin autenticación no es una barrera antifraude") — el punto acá es que **no se puede lanzar comercialmente con eso pendiente**.

**Reproducción (verificada):**

```
10 solicitudes de video gratis desde 10 IPs distintas → 10 aceptadas (202)
```

**Corrección**

`docs/LANZAMIENTO_WEB.md` ya tiene el diseño correcto (tablas `users`, `subscriptions`, `credit_ledger`, `jobs`, `webhook_events`). Hay que implementarlo. Mínimo viable para lanzar:

1. **Cuentas con email verificado.** Magic link alcanza; no hace falta contraseña.
2. **Cuota del lado del servidor** en la misma transacción que crea el trabajo:
   - reservar el crédito **antes** de encolar,
   - devolverlo si el trabajo termina en `error`,
   - consumirlo definitivamente al completar.
3. **`credit_ledger` como libro mayor append-only**, nunca un contador mutable. Necesario para auditar disputas de pago.
4. **Cuota anónima de contención** mientras se construye lo anterior: límite duro por IP + huella del navegador (p. ej. 3 videos / 24 h), en la base, no en memoria. No es antifraude serio, pero es infinitamente mejor que `localStorage`.
5. **Cuota para audio también** — hoy es el vector de abuso más barato.
6. Migrar SQLite → PostgreSQL antes de tener libro mayor de créditos (ver P1-14).

---

## P0-6 · Sin límite de cola ni de disco: un solo usuario llena el servidor

**Evidencia**

```python
# server/app/main.py:91
executor = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="pachevideo")
# :536
executor.submit(run_download, job_id, raw_url, payload.mode, payload.quality, payload.audioKbps, plan)
```

**Impacto**

`ThreadPoolExecutor` tiene una **cola ilimitada**. Con `WORKERS=2` y `MAX_FILE_BYTES=2 GiB`:

- Nada limita cuántos trabajos pendientes puede haber. Se puede encolar miles.
- Nada consulta el espacio libre en disco antes de aceptar un trabajo.
- La verificación de tamaño (`main.py:419`) ocurre **después** de escribir el archivo completo: para cuando se detecta el exceso, los 2 GB ya están en disco.
- `max_filesize` de yt-dlp **no cubre** descargas fragmentadas (HLS/DASH) ni el archivo fusionado final, así que el tope real no está garantizado.
- Un usuario con 20 URLs de 3 horas llena un volumen de 100 GB, y como el TTL es de 1 hora, el disco queda saturado ~1 hora. Todos los demás trabajos fallan con errores de escritura crípticos.
- La cola es **en memoria**: al reiniciar el contenedor, todo lo pendiente se pierde en silencio y esos trabajos quedan `queued` para siempre en la base.

**Corrección**

1. **Cola acotada + rechazo explícito.** Reemplazar por `queue.Queue(maxsize=N)` con workers propios, y devolver **HTTP 503 con `Retry-After`** cuando esté llena. Un 503 honesto es mejor que una espera de 40 minutos.
2. **Límite de trabajos activos por cuenta/IP** (p. ej. 1 concurrente en Gratis, 3 en Pro). Esto también da valor real al "procesamiento prioritario" que se vende.
3. **Verificar disco antes de aceptar:**
   ```python
   free = shutil.disk_usage(DOWNLOAD_DIR).free
   if free < MAX_FILE_BYTES * (pending_jobs + 1) * SAFETY:
       raise HTTPException(503, "Servicio saturado, probá en unos minutos")
   ```
4. **Cortar durante la descarga, no después.** Usar `progress_hook` para abortar en cuanto `downloaded_bytes > MAX_FILE_BYTES` (lanzar desde el hook detiene a yt-dlp), y aplicar `max_filesize` **por formato** además del tope global.
5. Bajar `MAX_DURATION_SECONDS` a algo defendible económicamente (30-60 min) hasta que haya facturación por uso.
6. Cuando la cola pase a durable (P1-14), reencolar en el arranque los trabajos que quedaron `queued`.

---

## P0-7 · El repositorio no tiene ni un solo commit — el pipeline de release no puede funcionar

**Evidencia**

```
$ git log --oneline -15
fatal: your current branch 'master' does not have any commits yet
$ git ls-files | wc -l
0
$ git remote -v
(vacío)
```

**Impacto**

Todo el árbol está sin seguimiento. No hay commits, no hay remoto, no hay historial. Consecuencias directas:

- `.github/workflows/release-macos.yml` se dispara con `push: tags: v*`. **No hay forma de crear ese tag**: el flujo documentado en el README (`git tag v0.5.0 && git push origin main --tags`) falla porque no hay commits ni remoto.
- El README apunta a `https://github.com/Pachecoins/PacheVideoPlugin.git` y `scripts/install-latest-macos.sh` descarga desde Releases de ese repo. Ese camino de instalación **no existe hoy**.
- No hay forma de revertir un deploy malo, ni de bisecar una regresión, ni de saber qué versión está en producción.
- Un `rm -rf` accidental, un disco que falla o un `git clean` borran el producto entero. **No hay copia en ningún otro lado.**

**Corrección — hacer esto hoy, antes que cualquier otra tarea de este informe**

1. Verificar que `.gitignore` cubre todo lo sensible. Ya cubre `server/data/`, `.venv-server/`, `dist/`, `*.p12`. Confirmar que ningún `.env` con el CBU real, claves Pro o certificados esté en el árbol.
2. `git add -A && git commit` inicial; crear el repositorio remoto **privado** y pushear.
3. Proteger `main`: requerir PR y checks en verde.
4. Configurar los secretos de Apple del README (`MACOS_CERTIFICATE_P12`, etc.) y **probar el workflow con `workflow_dispatch`** antes de depender de un tag.
5. Agregar el workflow de Windows que falta (hoy solo se construye macOS en CI; `scripts/build-windows-installer.ps1` únicamente corre a mano).
6. Agregar un job de CI que corra los tests (ver P1-16) y que sea obligatorio para mergear.

---

## P0-8 · yt-dlp está pineado sin ruta de actualización: el servicio se rompe solo

**Evidencia**

```
# server/requirements.txt
yt-dlp[default]==2026.7.4
```

```dockerfile
# server/Dockerfile:13-15
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

**Impacto**

Este es el riesgo operativo número uno de un producto construido sobre yt-dlp, y merece tratarse como defecto y no como "riesgo externo aceptado".

Las plataformas de origen cambian sus firmas, tokens y formatos **cada pocas semanas**. yt-dlp publica correcciones a los pocos días. Una versión pineada dentro de una imagen inmutable significa que el producto **deja de funcionar solo**, sin que nadie toque nada, típicamente en 2 a 6 semanas. Con suscripciones mensuales activas, eso es una ola de reembolsos y contracargos.

Agravantes concretos:

- `/api/health` (`main.py:483-494`) reporta la **versión** de yt-dlp pero nunca prueba una extracción real. El healthcheck del contenedor da verde mientras el 100 % de las descargas falla.
- El contenedor es `read_only: true` (`deploy/docker-compose.yml:19`) y `$HOME` no es escribible, así que **la caché de yt-dlp falla al escribir**. Eso rompe justo los mecanismos (caché de nsig, etc.) que hacen que yt-dlp se recupere de cambios en el origen.
- No hay alertas. El primer aviso va a ser un cliente enojado.

**Corrección**

1. **Canario de extracción.** Un chequeo periódico (cada 15 min) que corre `extract_info(download=False)` contra 2-3 URLs estables de las fuentes principales y expone el resultado en `/api/health` como `extractorOk`. Alertar cuando se ponga en rojo.
2. **Actualización sin redeploy.** Elegir uno:
   - reconstruir y desplegar la imagen automáticamente cada noche con la última `yt-dlp`, o
   - montar yt-dlp en un volumen escribible y actualizarlo con un job programado, con capacidad de rollback.
3. **Arreglar la caché:** `ENV XDG_CACHE_HOME=/tmp` en el Dockerfile (ya existe `tmpfs` en `/tmp`), o `"cachedir": "/tmp/yt-dlp-cache"` en las opciones.
4. **Runbook escrito**: qué hacer cuando la extracción se cae — banner de estado en la web, pausar cobros nuevos, actualizar, verificar.
5. Comunicar la dependencia externa en los términos: el servicio depende de plataformas de terceros y puede degradarse sin aviso.

---

# P1 — Corregir antes del registro público

## P1-1 · Fuga de memoria en el limitador de tasa

`server/app/main.py:92` — `rate_windows: dict[str, deque[float]] = defaultdict(deque)` nunca se purga. Cada IP nueva agrega una clave permanente.

**Verificado:** tras 5000 IPs distintas quedan 5000 claves en memoria, ninguna se libera.

**Fix:** purgar las ventanas vacías dentro de `consume_rate_limit`, o usar un `TTLCache` acotado, o mover el rate limiting al borde (Caddy/Cloudflare) que es donde corresponde.

## P1-2 · Una escritura en SQLite por cada callback de progreso

`server/app/main.py:320-328` llama a `update_job()` en **cada** invocación del hook de yt-dlp. `update_job` (`:160-166`) **abre una conexión SQLite nueva, escribe y cierra** cada vez.

**Verificado:** 500 `update_job()` = 0,48 s (~1 ms c/u), abriendo una conexión por llamada. yt-dlp dispara el hook cientos o miles de veces por descarga. Además el journal mode es `delete`, **no WAL**, así que lectores y escritores se bloquean mutuamente — y el frontend hace polling cada 900 ms sobre la misma base.

**Fix:**
1. `PRAGMA journal_mode=WAL` y `PRAGMA synchronous=NORMAL` en `initialize_database()`.
2. Throttlear el hook: escribir a lo sumo cada 1 s o cada 2 % de avance.
3. Mantener el progreso en memoria y persistir solo las transiciones de estado.
4. Reutilizar una conexión por hilo (`threading.local`) en vez de abrir una por operación.

## P1-3 · Los errores crudos de yt-dlp se devuelven al cliente

`server/app/main.py:437-438` guarda `str(error)` en `detail` y `error`, y `public_job` (`:183-187`) lo devuelve tal cual. Los mensajes de yt-dlp incluyen rutas del sistema de archivos del servidor, URLs internas de CDN, nombres de extractores y a veces fragmentos de respuesta.

**Fix:** mapear a un catálogo cerrado de mensajes en español para el usuario (`fuente_no_soportada`, `contenido_privado`, `limite_excedido`, `error_temporal`), y loguear el detalle técnico del lado del servidor asociado al `job_id`.

## P1-4 · El servidor no tiene logging estructurado

A diferencia del companion (que sí configura `YtDlpLogger`, `companion/server.py:82-93`), `server/app/main.py` **no pasa `logger`** a yt-dlp y no configura logging propio.

**Verificado:** durante las pruebas, yt-dlp escribió `ERROR: [generic] v: Unable to download webpage: HTTP Error 404` directo a stderr a pesar de `quiet: True` y `no_warnings: True`.

Resultado: sin logs de acceso, sin logs de trabajos, sin IDs de correlación, sin métricas, sin trazas. Diagnosticar un incidente en producción va a ser adivinar. Y las URLs de origen de los usuarios terminan en stderr sin control — un problema de privacidad además de operativo.

**Fix:** logging JSON estructurado con `job_id`/`request_id`; pasar un `logger` propio a yt-dlp; exponer métricas Prometheus (trabajos por estado, duración, tasa de error por extractor, profundidad de cola, disco libre); conectar Sentry o equivalente.

## P1-5 · Dos bucles de polling simultáneos en el frontend

`web/app/components/downloader-app.tsx:101-127` — `startDownload()` no hace `clearTimeout(pollTimer.current)` antes de arrancar. Si el usuario pulsa "Reintentar ahora" (`:285`) o inicia otra descarga con una en curso, quedan **dos bucles de polling activos** pisándose el `setJob`. Se ve como progreso que retrocede o un trabajo "completo" que vuelve a "descargando".

**Fix:** limpiar el timer al inicio de `startDownload()` y usar un `AbortController` + un token de generación para descartar respuestas de bucles viejos.

## P1-6 · La PWA no cumple los requisitos de instalación

- `web/public/manifest.webmanifest` declara **un solo icono de 165×165**. Chrome y Android exigen 192×192 y 512×512 para ofrecer "Agregar a inicio". La instalación va a fallar en silencio.
- `web/public/sw.js` es un stub de dos líneas sin handler `fetch`: no hay offline, no hay caché, no hay resiliencia.
- `server/tests/test_deploy.py:22-32` **cristaliza el bug**: afirma que el manifiesto coincide con las dimensiones de `logo.png`, así que arreglar el icono rompe el test.
- `docs/ROADMAP_SALIDA_AL_MERCADO.md` ya lista "iconos 192/512" como pendiente, pero la web se vende como "instalable" hoy.

**Fix:** generar iconos 192/512 (más un `maskable`), declararlos todos, escribir un service worker real (app shell cacheado, `no-store` para `/api/*`), reescribir el test para que exija los tamaños requeridos, y verificar la instalación en iOS Safari y Android Chrome.

## P1-7 · Las descargas se hacen pasar por el Worker de Cloudflare

`web/app/api/jobs/[id]/download/route.ts` transmite el archivo completo a través del Worker. Con archivos de hasta 2 GB eso consume tiempo de CPU y egreso del Worker por cada descarga, con costos y límites de plataforma que no aparecen en `docs/ESTIMACION_INFRAESTRUCTURA.md`.

Peor: hay **dos caminos distintos** según la configuración. `web/app/api/jobs/[id]/route.ts:24` deriva al usuario **directo al backend** cuando `PACHEVIDEO_PUBLIC_BASE_URL` es HTTPS, saltándose el proxy. Es decir, la ruta que se ejercita en desarrollo no es la que corre en producción.

**Fix:** elegir un solo camino. Lo recomendable es almacenamiento de objetos (R2/S3) con URLs prefirmadas de vida corta: saca el tráfico pesado del Worker y del backend, sobrevive a reinicios y escala horizontalmente. Es además el prerrequisito para pasar de 1 servidor a N.

## P1-8 · No hay Términos, Privacidad ni política de DMCA — y el checkbox de aceptación fue eliminado

No existen `/terminos`, `/privacidad` ni `/dmca`. Peor: el test `web/tests/rendered-html.test.mjs:38` afirma explícitamente

```js
assert.doesNotMatch(html, /Confirmo que el contenido es mío|type="checkbox"/i);
```

es decir, la aceptación de términos **se quitó a propósito y el test impide que vuelva**. Al mismo tiempo `scripts/smoke-webapp.py:29` sigue enviando `acceptedTerms: True`, un campo que `CreateJob` ni siquiera define — evidencia de que la funcionalidad existió y se removió a medias.

Todo pasarela de pago (Mercado Pago, Stripe) exige Términos y Privacidad publicados. Sin un canal DMCA/notice-and-takedown y sin registro de aceptación del usuario, la responsabilidad por el contenido descargado recae directamente sobre el operador.

**Fix:** publicar Términos, Privacidad y contacto DMCA; reinstaurar la aceptación explícita en el primer uso y **registrarla** (timestamp + versión de los términos + cuenta); actualizar el test para exigirla; alinear el smoke test.

## P1-9 · La caché de yt-dlp no puede escribir en el contenedor de solo lectura

`deploy/docker-compose.yml:19` fija `read_only: true` con `tmpfs` solo en `/tmp`. El home de `pachevideo` no es escribible, así que `~/.cache/yt-dlp` falla. Eso desactiva exactamente los mecanismos de caché que ayudan a yt-dlp a recuperarse de cambios en el origen.

**Fix:** `ENV XDG_CACHE_HOME=/tmp/cache` en el Dockerfile, o pasar `"cachedir"` explícito. Verificar también que `/tmp` con 512 MB alcanza para el trabajo temporal de FFmpeg en archivos grandes.

## P1-10 · El modo audio puede entregar un archivo que no es MP3

`server/app/main.py:281-291` — si la conversión con `FFmpegExtractAudio` falla pero el `.webm` original quedó en disco, la rama de respaldo toma "el archivo más reciente que no termine en `.part`" y lo sirve. El usuario pidió MP3 320 kbps y recibe un `.webm` con `Content-Type: application/octet-stream`, que no le va a abrir en el reproductor.

**Fix:** validar que la extensión de salida coincida con la solicitada. Si no coincide, tratarlo como error y reintentar. Agregar un test que lo cubra.

## P1-11 · SSRF residual por rebinding de DNS y redirecciones

`server/app/main.py:197-213` valida bien lo básico — verifiqué que `ip.is_global` rechaza correctamente `127.0.0.1`, `169.254.169.254` (metadata de nube), `100.64.0.0/10`, `198.18.0.0/15` y `::ffff:127.0.0.1`. Es una implementación mejor que el promedio.

Pero quedan tres huecos:
1. **TOCTOU.** `getaddrinfo()` se llama una vez; yt-dlp resuelve **de nuevo** al conectar. Un DNS con TTL bajo puede devolver una IP pública en la validación y una privada en la descarga.
2. **Redirecciones.** Solo se valida la URL inicial. yt-dlp sigue redirecciones y descarga de CDNs arbitrarios sin volver a validar.
3. `parsed.port or 443` (`:207`) usa el puerto 443 aunque el esquema sea `http`, lo que puede dar una resolución distinta a la real.
4. `ALLOWED_HOSTS` está **vacío por defecto** (verificado): sin configurarlo se acepta cualquier dominio público.

**Fix:** la mitigación real es de red, no de código — **firewall de egreso** que bloquee RFC1918, loopback, link-local y los rangos de metadata de la nube desde el contenedor del API. Eso cierra 1 y 2 de una. Complementar con `ALLOWED_HOSTS` poblado en producción (además reduce superficie legal) y corregir el puerto según esquema.

## P1-12 · Sin backups ni durabilidad

`pachevideo_data` es un volumen local de Docker. SQLite sin réplica, sin backup, sin punto de recuperación. La cola vive en memoria. Un fallo del host pierde base y archivos.

**Fix:** migrar a PostgreSQL gestionado con backups automáticos (obligatorio antes del libro mayor de créditos de P0-5); objetos a R2/S3; cola durable (tabla de trabajos con locking, o Redis/RQ); probar la restauración de verdad, no solo configurarla.

## P1-13 · No hay CI que corra los tests

`.github/workflows/release-macos.yml` es el único workflow: construye instaladores de macOS. **Nada** corre los tests de Python, el `npm run test` de la web, ni el lint. No hay CI de Windows.

Además la suite de Python no se puede descubrir tal como está: falta `server/tests/__init__.py` (`python -m unittest discover` falla con `Start directory is not importable`), `test_deploy.py:7` importa `yaml` que **no está en ningún `requirements.txt`**, y no hay comando de test documentado en el README.

**Verificado:** con las dependencias instaladas a mano, 19 de 20 tests pasan (el único fallo fue por un archivo que no stagé). La calidad de los tests existentes es buena; el problema es que nadie los corre automáticamente.

**Fix:** agregar `server/tests/__init__.py`, mover `pyyaml` a un `requirements-dev.txt`, documentar el comando, y crear un workflow `ci.yml` que corra tests de Python, tests de la web y ESLint en cada PR, obligatorio para mergear.

## P1-14 · El helper local sale en silencio si el puerto está ocupado

```python
# companion/server.py:476-479
except OSError as error:
    LOGGER.exception("Could not bind %s:%s", HOST, PORT)
    return          # ← sale con código 0
```

La app de escritorio (`companion/desktop.py:262-292`) reintenta 18 veces y luego muestra "Helper desconectado" sin explicar por qué. El usuario no tiene forma de saber que otro proceso ocupa el 18765.

**Fix:** salir con código distinto de cero, escribir un mensaje accionable en el log, y hacer que el helper pruebe puertos alternativos publicando el elegido en el archivo de sesión que lee el cliente.

## P1-15 · El diccionario de trabajos del helper nunca se purga

`companion/server.py:141` — `jobs: dict[str, Job] = {}` crece indefinidamente mientras el helper esté abierto (arranca con Windows por defecto, así que puede correr semanas). Cada `Job` retiene URL, rutas y mensajes de error.

**Fix:** purgar trabajos terminados a los 30 minutos; tope duro de entradas.

## P1-16 · Carpetas temporales huérfanas en la máquina del usuario

`companion/server.py:230-231` crea `.pachevideo-<id>` **dentro de la carpeta de descargas del usuario**. Si el helper se mata a mitad de camino, esas carpetas quedan con descargas parciales que nadie limpia.

**Fix:** usar el directorio temporal del sistema y mover el resultado final; barrer carpetas `.pachevideo-*` viejas al arrancar.

## P1-17 · Sin cancelación de trabajos

Ni la web ni el escritorio permiten cancelar. Un usuario que pegó la URL equivocada de un video de 3 horas ocupa un worker de los dos disponibles hasta el final. Es a la vez un problema de UX y un vector de abuso barato.

**Fix:** `DELETE /api/jobs/{id}` con token, que marca el trabajo cancelado, aborta yt-dlp desde el `progress_hook` y limpia la carpeta. Botón "Cancelar" en la tarjeta de progreso.

---

# P2 — Deuda técnica de las primeras semanas

**P2-1 · Caddy comprime video inútilmente.** `deploy/Caddyfile:2` — `encode zstd gzip` sin filtro por tipo de contenido intenta comprimir MP4/MP3, que ya están comprimidos. Es CPU quemada en cada descarga. Restringir con `match` a `text/*`, `application/json`, `application/javascript`.

**P2-2 · Sin rate limiting ni timeouts en el borde.** El Caddyfile no configura límites de conexión, de tasa ni timeouts de proxy. Toda la protección depende del limitador en proceso, que es justo el que P0-3 rompe.

**P2-3 · Sin cabeceras de seguridad en la web.** El Caddyfile pone HSTS y `nosniff` en el **API**, pero la app web no tiene CSP, `X-Frame-Options` ni `Permissions-Policy`.

**P2-4 · El plugin de Premiere está huérfano.** `plugin/` no se menciona en el README (que aclara que el instalador de Windows "no requiere UXP"), pide `network.domains: "all"` (`plugin/manifest.json:44`), y apunta a `http://127.0.0.1:18765` en texto plano. O se mantiene y se documenta, o se saca del árbol.

**P2-5 · Andamiaje muerto de la plantilla.** `web/db/`, `web/drizzle/`, `web/examples/d1/`, `web/next.config.ts` (el proyecto usa vinext/vite, no Next config) y la optimización de imágenes en `web/worker/index.ts` no se usan. Ensucian el árbol y suman dependencias.

**P2-6 · Textos comerciales inconsistentes.** `docs/LANZAMIENTO_WEB.md` dice "10 descargas de por vida" mientras la UI y `docs/MVP_PRODUCTO.md` dicen "1 video de prueba" — y el test `rendered-html.test.mjs:32` prohíbe activamente la variante de 10. La landing (`web/app/page.tsx:141`) vende "Aplicación para Windows y macOS" como beneficio Pro, pero los instaladores son de descarga libre y sin licenciamiento.

**P2-7 · `mkdir(exist_ok=False)` con `rmtree` en el `except`.** `server/app/main.py:304` y `:432` — si el `mkdir` falla por permisos (no por colisión), el manejador borra recursivamente una carpeta que quizá no creó este trabajo. La colisión de UUID4 es despreciable, pero el manejo es peligroso. Crear la carpeta antes del `try`, o distinguir el tipo de `OSError`.

**P2-8 · El smoke test depende de un tercero.** `scripts/smoke-webapp.py:15` usa `samplelib.com`. Si ese sitio se cae, el smoke test miente. Servir un archivo de muestra desde infraestructura propia. Además envía `acceptedTerms`, campo que ya no existe en el modelo.

**P2-9 · `/api/health` no prueba nada real.** Reporta versiones y flags, pero no verifica que la extracción funcione ni que haya disco libre. El healthcheck de Docker (`server/Dockerfile:21-22`) da verde con el servicio totalmente roto. Ver P0-8.

---

# P3 — Prolijidad

**P3-1** · `server/app/main.py:429` usa `attempt` fuera del alcance del `for`. Funciona, pero es frágil y los linters lo marcan.
**P3-2** · Sin versionado de API (`/api/v1/...`). Cambiar el contrato con clientes de escritorio instalados va a ser doloroso.
**P3-3** · Mensajes de usuario en español embebidos en el código, sin infraestructura de i18n. Fijar el criterio antes de que se multipliquen.
**P3-4** · `web/app/chatgpt-auth.ts` no lo importa nadie. Confirmar si es residuo de la plantilla y borrarlo.

---

# Riesgos externos que no se pueden eliminar

Estos no son defectos del código. Van acá porque afectan la decisión de lanzamiento y hay que tomar posición explícita.

| Riesgo | Por qué importa | Mitigación posible |
|---|---|---|
| **Términos de las plataformas de origen** | La vista previa de la landing (`web/app/page.tsx:61`) muestra `https://youtu.be/tu-video`. Publicitar un descargador de YouTube **de pago** es un perfil legal muy distinto al de una herramienta genérica. | Quitar toda referencia a plataformas específicas del material comercial. Poblar `PACHEVIDEO_ALLOWED_HOSTS` con fuentes defendibles. Asesoramiento legal antes de facturar. |
| **Riesgo con la pasarela de pago** | Mercado Pago y Stripe suspenden cuentas de servicios de descarga. Sin ToS/Privacidad/DMCA (P1-8) el riesgo se multiplica. | Publicar los textos legales antes de solicitar la cuenta comercial. Tener un procesador de respaldo. |
| **Ruptura de extractores** | Fuera de tu control por diseño. P0-8 es la parte que **sí** controlás: detectarla rápido y actualizar rápido. | Canario + alertas + actualización automatizada + página de estado. |
| **Costo de egreso** | Videos de 2 GB por descarga. `docs/ESTIMACION_INFRAESTRUCTURA.md` tiene fórmulas de capacidad, pero el proxy por Worker (P1-7) no está contemplado. | Almacenamiento de objetos con egreso barato; medir antes de escalar. |
| **Reventa de códigos Pro** | Los códigos de `PACHEVIDEO_PRO_ACCESS_KEYS` no están atados a ninguna identidad. Un cliente puede compartir el suyo con 100 personas. | Solo viable para una beta chica y conocida. Cuentas reales antes de escalar (P0-5). |

---

# Plan de implementación sugerido para Codex

Ordenado por dependencia, no por prioridad. Cada bloque debería ser un PR revisable.

### Bloque 0 — Hoy (30 minutos)
- [ ] **P0-7**: commit inicial, repositorio remoto privado, push. Nada más hasta que esto esté.

### Bloque 1 — Seguridad (1-2 días)
- [ ] **P0-2**: token de sesión + validación de `Host` + allowlist de `outputFolder` + saneado de nombres en `companion/server.py`. **Bloquea la firma del instalador.**
- [ ] **P0-1**: quitar la clave hardcodeada de `web/app/pro/page.tsx`; actualizar `rendered-html.test.mjs`.
- [ ] **P1-3**: catálogo cerrado de mensajes de error de cara al usuario.
- [ ] **P1-11**: firewall de egreso en el host del API; corregir el puerto según esquema.

### Bloque 2 — Estabilidad del servicio (2-3 días)
- [ ] **P0-3**: header de IP unificado, precedencia con paréntesis, allowlist de proxies, token interno web↔API.
- [ ] **P0-4**: el limpiador ignora trabajos activos; `expires_at` se recalcula al completar; barrido separado de zombis.
- [ ] **P0-6**: cola acotada con 503 + `Retry-After`; verificación de disco; corte de tamaño durante la descarga.
- [ ] **P1-1**, **P1-2**: purga del limitador; WAL + throttling del progreso.
- [ ] **P1-4**: logging estructurado + métricas + Sentry.

### Bloque 3 — Resiliencia de yt-dlp (1 día)
- [ ] **P0-8**: canario de extracción en `/api/health`; actualización automatizada; `XDG_CACHE_HOME`; runbook.
- [ ] **P1-9**, **P1-10**: caché escribible; validación de extensión de salida.

### Bloque 4 — Modelo comercial (3-5 días, el más largo)
- [ ] **P0-5**: cuentas con email verificado; cuota del lado del servidor; `credit_ledger`; cuota de contención por IP como paso intermedio.
- [ ] **P1-12**: PostgreSQL + backups; objetos a R2/S3; cola durable.
- [ ] **P1-8**: Términos, Privacidad, DMCA + registro de aceptación.

### Bloque 5 — Producto y entrega (1-2 días)
- [ ] **P1-5**: arreglar el doble polling.
- [ ] **P1-6**: iconos 192/512, service worker real, reescribir `test_deploy.py`.
- [ ] **P1-7**: un solo camino de descarga (preferentemente URLs prefirmadas).
- [ ] **P1-13**: CI con tests + lint, obligatorio; workflow de Windows.
- [ ] **P1-14** a **P1-17**: robustez del helper y cancelación de trabajos.

---

# Pruebas mínimas que deben pasar antes de lanzar

Ninguna de estas existe hoy. Son la definición de "listo".

### Seguridad
1. `POST http://127.0.0.1:18765/downloads` **sin** token de sesión → 401.
2. Igual pero con `Origin: https://evil.example` → rechazado.
3. `outputFolder` apuntando a la carpeta de Inicio de Windows, a `/System` o a `Program Files` → 400.
4. Título de origen con `../`, `:` y separadores de ruta → el archivo aterriza saneado dentro del destino permitido.
5. `GET /pro` → el HTML **no** contiene ninguna cadena que matchee `/PACHE-PRO-|proAccessKey/`.
6. `POST /api/jobs` con `url` que resuelve a `169.254.169.254`, `127.0.0.1` y `10.0.0.1` → 400 en los tres.
7. `POST /api/jobs` **sin** el token interno del proxy, desde fuera de la red de confianza → 403.
8. `GET /api/jobs/{id}?token=<incorrecto>` → 404 (nunca 403, para no confirmar existencia).

### Límites y cuotas
9. Con la cuota consumida, `POST /api/jobs` desde `curl` (sin navegador) → 402/403. **La cuota debe imponerse en el servidor.**
10. 30 requests desde 30 IPs distintas vía el proxy en un minuto → **las 30 aceptadas** (regresión de la cubeta compartida).
11. 30 requests desde **una** IP en un minuto → las que exceden el límite → 429.
12. `cf-connecting-ip` falsificado desde fuera de la allowlist de proxies → el header se ignora, el límite se aplica igual.
13. Llenar la cola hasta el máximo → el siguiente `POST` devuelve 503 con `Retry-After`.
14. Encolar cuando el disco libre es menor al umbral → 503, y **ningún** archivo parcial escrito.
15. Descargar una fuente que supera `MAX_FILE_BYTES` → abortada **durante** la transferencia, no después.

### Ciclo de vida de los trabajos
16. Trabajo cuya descarga excede `JOB_TTL_SECONDS` → **completa igual**; la fila no se borra mientras esté activa.
17. `expires_at` de un trabajo completado se recalcula desde el momento de completar.
18. Trabajo atascado en `downloading` más allá del deadline de procesamiento → marcado `error`, carpeta limpia, sin huérfanos.
19. Reiniciar el API con trabajos en cola → se reencolan o se marcan `error`; ninguno queda `queued` para siempre.
20. Cancelar un trabajo en curso → yt-dlp se detiene, la carpeta se borra, el worker se libera.

### Funcionalidad
21. Smoke completo video + audio contra un archivo de muestra **propio**, verificando extensión, tamaño y reproducibilidad.
22. Modo audio con FFmpeg fallando a propósito → el trabajo termina en `error`, **nunca** entrega un `.webm` disfrazado de MP3.
23. Descarga con `Range` (pausar/reanudar en móvil) → 206 con `Content-Range` correcto.
24. Iniciar una descarga con otra en curso → un solo bucle de polling, sin progreso que retroceda.
25. Canario de extracción contra las fuentes reales → `extractorOk: true` en `/api/health`.

### Plataforma
26. Auditoría Lighthouse PWA → instalable, con iconos 192 y 512 presentes.
27. Instalación real en iOS Safari y Android Chrome desde HTTPS.
28. Instalador de Windows: instalar → descargar → desinstalar → verifica que no queden restos.
29. `.pkg` de macOS firmado y notarizado se instala sin advertencias de Gatekeeper.
30. Restauración de backup: destruir la base y restaurarla; los trabajos completos siguen descargables.

---

## Nota final

La base técnica de PacheVideo es sólida — la clasificación de errores transitorios vs permanentes, el respaldo automático a formato compatible, el ocultamiento de los reintentos al usuario y el endurecimiento del contenedor son decisiones de alguien que pensó el problema en serio. Los documentos de `docs/` ya identifican con honestidad la mayor parte de lo que falta.

La brecha no está en la ingeniería del camino feliz. Está en **hacer cumplir lo que se vende** (P0-1, P0-5), **sobrevivir al primer día de tráfico real** (P0-3, P0-4, P0-6) y **no distribuir un binario vulnerable** (P0-2). Esos tres frentes son la diferencia entre un lanzamiento y un incidente.
