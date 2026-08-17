# PacheVideo Web: monetización, capacidad y lanzamiento

## Modelo comercial recomendado

| Plan | Audio | Video | Publicidad | Prioridad |
|---|---|---|---|---|
| Gratis | No consume créditos | 5 descargas de por vida hasta 1080p por cuenta registrada | Sí | Normal |
| Pro | No consume créditos | Sin cupo mensual, sujeto a uso razonable | No | Alta |

Precio inicial de Pro: **ARS 9.999,99 por mes**. El importe debe ser configurable sin publicar una nueva versión, porque la infraestructura se paga en moneda dura y el precio necesita revisión periódica.

El visitante puede probar 1 video hasta 1080p sin tarjeta. El incentivo de registro entrega después un cupo nuevo de 5 videos hasta 1080p, no una prueba por días. Reduce la fricción y convierte el uso gratuito en cuentas recuperables.

## Cómo funcionan los créditos

1. Cada cuenta verificada recibe 5 créditos de video una sola vez.
2. Audio cuesta 0 créditos, pero mantiene límites técnicos de concurrencia y tamaño.
3. Al encolar un video se reserva 1 crédito.
4. Si el trabajo falla o se cancela antes de producir el archivo, la reserva se devuelve.
5. Si termina correctamente, la reserva pasa a consumida.
6. Una suscripción Pro activa no consume créditos.
7. Al vencer o cancelarse Pro, la cuenta conserva el saldo gratuito que todavía tenía.

El saldo nunca se guarda como un número que se modifica sin historial. Se usa un libro mayor (`credit_ledger`) para poder auditar altas, reservas, consumos y devoluciones.

Tablas mínimas:

- `users`: identidad, email verificado y estado.
- `subscriptions`: proveedor, identificador externo, estado y período vigente.
- `credit_ledger`: movimientos firmes e idempotentes.
- `jobs`: dueño, tipo, estado, costo en créditos y tiempos.
- `webhook_events`: eventos de pago ya procesados para evitar duplicados.

## Pago mensual

Mercado Pago permite crear un plan recurrente mensual en ARS y notificar cambios mediante webhooks. El backend debe ser la única fuente de verdad: la interfaz no habilita Pro por volver de la pantalla de pago, sino después de validar el evento del proveedor.

Flujo:

1. El usuario inicia sesión y elige Pro.
2. El backend crea o recupera el plan y genera el checkout.
3. Mercado Pago cobra y envía un webhook.
4. El backend verifica la firma, guarda el evento de forma idempotente y actualiza `subscriptions`.
5. La siguiente solicitud obtiene los beneficios Pro.

Nunca guardar números de tarjeta en PacheVideo.

## Publicidad

Para el MVP se reserva un bloque claramente rotulado **PUBLICIDAD**, separado del botón y del enlace final de descarga. El plan Pro no renderiza el script publicitario.

La opción más controlable para el comienzo son patrocinios directos o anuncios propios. AdSense puede no aprobar un descargador genérico: sus políticas prohíben monetizar páginas que ayuden a descargar streaming cuando el proveedor lo prohíbe y también prohíben anuncios que puedan confundirse con botones de descarga.

Reglas operativas:

- No colocar anuncios al lado, encima o debajo del botón de descarga.
- No pedir ni premiar clics en anuncios.
- No hacer que un anuncio no recompensado sea obligatorio para liberar el archivo.
- Mostrar anuncios solo a usuarios Gratis.
- Reservar el tamaño del bloque para evitar saltos de diseño.
- Cargar el proveedor de anuncios de forma diferida.
- Implementar consentimiento, privacidad y opción de anuncios no personalizados cuando corresponda.
- Mantener una política explícita de contenido propio o autorizado y un canal de denuncias.

## ¿Alcanza un solo servidor?

Para una beta, sí. Para una explosión de tráfico, no.

Un VPS de 4 vCPU y 8 GB con dos trabajos simultáneos puede validar el producto. La cola evita que un pico derribe el proceso, pero no aumenta la capacidad: si llegan más trabajos que los que terminan, el tiempo de espera crece.

Fórmula útil:

```text
trabajos por hora ≈ workers × 3600 / segundos promedio por trabajo
```

Ejemplo ilustrativo: dos workers y seis minutos promedio permiten alrededor de 20 trabajos por hora. Hay que medir con contenido real; resolución, codec, duración, fuente y ancho de banda cambian mucho el resultado.

### Arquitectura para crecer

```text
Web / PWA
    |
API sin estado + autenticación + cuotas
    |
Cola durable  -----> PostgreSQL
    |
Workers FFmpeg escalables (cola Gratis y cola Pro prioritaria)
    |
Object storage temporal (S3/R2) + CDN
```

Los workers suben el resultado al almacenamiento de objetos y entregan una URL firmada con vencimiento. No conviene servir todos los archivos desde el mismo VPS que procesa FFmpeg.

Controles mínimos:

- Gratis: 1 trabajo simultáneo por usuario.
- Pro: 2 trabajos simultáneos por usuario y prioridad de cola.
- Audio: 0 créditos, con límite de frecuencia, duración y tamaño.
- Video Pro: sin cupo mensual, con política de uso razonable contra automatización o reventa.
- Límite global de workers para impedir una factura inesperada.
- Archivos temporales borrados automáticamente después de una hora.
- Métricas de cola, tiempo de proceso, errores, CPU, egreso y costo por trabajo.

## Paso a paso para publicar

### 1. Validar localmente

Backend, desde la raíz:

```powershell
py -3.12 -m venv .venv-server
.\.venv-server\Scripts\python.exe -m pip install -r .\server\requirements.txt
$env:PACHEVIDEO_DATA_DIR = "$PWD/server/data"
$env:PACHEVIDEO_PUBLIC_BASE_URL = "http://127.0.0.1:8080"
$env:PACHEVIDEO_ALLOWED_ORIGINS = "http://localhost:3000"
.\.venv-server\Scripts\python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8080
```

Web, en otra terminal:

```powershell
cd web
npm ci
$env:PACHEVIDEO_API_URL = "http://127.0.0.1:8080"
npm run dev
```

Abrir `http://localhost:3000`.

### 2. Preparar la beta pública

1. Registrar el dominio y crear `api.pachevideo.com`.
2. Contratar un VPS Ubuntu con 4 vCPU, 8 GB de RAM y al menos 100 GB de disco.
3. Instalar Docker Engine y el complemento Docker Compose desde el repositorio oficial.
4. Apuntar el registro DNS A de `api.pachevideo.com` a la IP del VPS.
5. Clonar el repositorio en el servidor.
6. Copiar `deploy/.env.example` como `deploy/.env` y reemplazar dominio, origen web y límites.
7. Iniciar la API y Caddy:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

8. Verificar `https://api.pachevideo.com/api/health`.
9. Publicar `web/` con `PACHEVIDEO_API_URL=https://api.pachevideo.com`.
10. Crear cuentas, créditos y pagos antes de abrir el sitio a tráfico anónimo masivo.

### 3. Antes de vender

- Condiciones de servicio, privacidad, cookies y política de contenido autorizado.
- Email verificado, recuperación de cuenta y eliminación de cuenta.
- Webhooks de Mercado Pago probados en modo sandbox y producción.
- Copias de seguridad de PostgreSQL.
- Alertas de caída, tasa de errores y cola acumulada.
- Prueba de carga que simule trabajos cortos, medios y largos.
- Presupuesto máximo de infraestructura y apagado de emergencia.
- Soporte y proceso de reembolso/cancelación.

### 4. Señales para abandonar el VPS único

Migrar a la arquitectura con cola y workers escalables cuando ocurra cualquiera de estas señales:

- La cola supera cinco minutos de espera de forma sostenida.
- CPU permanece por encima de 80% durante 15 minutos.
- El disco temporal supera 70%.
- Los usuarios Pro esperan detrás de usuarios Gratis.
- El costo o el egreso por descarga deja de ser predecible.
