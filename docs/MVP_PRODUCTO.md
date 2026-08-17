# MVP de PacheVideo

## Producto que se lanza

PacheVideo usa un único motor de descargas y lo presenta en dos canales:

1. **PacheVideo Web**: funciona desde celular o computadora y procesa en la nube.
2. **PacheVideo Escritorio**: aplicación instalable para Windows y macOS que procesa localmente.

El producto tiene dos niveles comerciales:

| Nivel | Audio | Video | Publicidad | Procesamiento |
|---|---|---|---|---|
| Gratis | MP3 hasta 320 kbps | 5 videos hasta 1080p por cuenta registrada | Sí | Estándar |
| Video Pro | MP3 hasta 320 kbps | 1080p, 2K, 4K y máxima disponible; listas de hasta 20 enlaces y sin cupo mensual con uso razonable | No | Prioritario |

La aplicación de escritorio se entrega como parte de Video Pro. La landing y la web pueden probarse sin instalar nada.

## Qué está implementado

- Landing comercial y descargador web responsive/PWA.
- API FastAPI con descarga, conversión, enlace temporal y limpieza automática.
- Aplicación de escritorio e instaladores para Windows y macOS.
- Gratis limitado por el servidor a video de hasta 1080p y a 5 usos por cuenta registrada.
- Un visitante puede probar 1 video; al registrarse recibe un cupo nuevo completo de 5 videos.
- Video Pro se decide mediante el estado de suscripción guardado en el servidor.
- El consumo gratuito se guarda en el servidor y no depende del navegador.
- Hasta 3 intentos automáticos por trabajo con espera progresiva.
- Cambio automático a un formato compatible en los reintentos de video.
- Reconexión automática de la web si se corta el seguimiento de un trabajo.
- Descargas de escritorio aisladas en carpetas temporales; no se pisan archivos existentes.

## Qué no se debe presentar como terminado todavía

- La configuración de las credenciales privadas, el dominio y el Webhook de Mercado Pago sigue pendiente antes de cobrar en producción.
- El acceso por email está implementado, pero antes del lanzamiento hay que configurar las credenciales de Supabase y probar alta, regreso y cierre de sesión en producción.

## Cómo habilita Video Pro

PacheVideo crea la suscripción mensual mediante Mercado Pago y vincula su estado
a la sesión del cliente. El servidor consulta el estado real de Mercado Pago al
recibir un Webhook; solo `authorized` permite `1440`, `2160` o `max`.

La configuración y la prueba de punta a punta están documentadas en
[`MERCADO_PAGO_SUSCRIPCIONES.md`](MERCADO_PAGO_SUSCRIPCIONES.md).

## Reintentos y recuperación

Cada descarga usa dos niveles de recuperación:

1. yt-dlp reintenta red, fragmentos, extracción y acceso a archivos.
2. PacheVideo ejecuta hasta 3 ciclos completos. Desde el segundo usa un formato de video de archivo único, que suele recuperar rechazos de streams separados.

Las esperas predeterminadas son 1,5 y 3 segundos. Se configuran con:

```text
PACHEVIDEO_DOWNLOAD_ATTEMPTS=10
PACHEVIDEO_RETRY_BASE_SECONDS=1.5
PACHEVIDEO_RETRY_MAX_SECONDS=20
```

No se reintentan errores permanentes conocidos, como URL no compatible, video privado, contenido no disponible o inicio de sesión obligatorio.

## Camino exacto desde este MVP hasta cobrar automáticamente

### Etapa 1 — Beta técnica

- Publicar web y API con HTTPS.
- Probar enlaces públicos y autorizados de cada fuente admitida.
- Medir tasa de éxito, tiempo, tamaño y costo por trabajo.
- Invitar entre 20 y 50 usuarios conocidos.

Salida de etapa: al menos 95% de los casos admitidos terminan correctamente o devuelven una explicación accionable.

### Etapa 2 — Cuentas y prueba real

- Registro e inicio de sesión.
- Cinco videos gratis hasta 1080p por cuenta registrada.
- Estado de plan guardado en la base, no enviado por el navegador.
- Sesiones seguras, recuperación de cuenta y cierre de sesión en todos los dispositivos.
- Historial mínimo de consumo, sin conservar archivos vencidos.

Salida de etapa: el límite Gratis no se puede evitar cambiando el navegador o modificando una solicitud.

### Etapa 3 — Cobro

- Crear la cuenta comercial de Mercado Pago.
- Implementar checkout de suscripción.
- Validar webhooks firmados e idempotentes.
- Activar Pro sólo después de confirmar el pago en el servidor.
- Suspender Pro ante cancelación o pago vencido, manteniendo acceso Gratis.
- Agregar facturación, precio final, baja y soporte.

Salida de etapa: compra, renovación, cancelación y pago rechazado pasan pruebas automáticas.

### Etapa 4 — Aplicación Pro

- La app inicia sesión contra la misma cuenta de la web.
- Obtiene una autorización corta y verificable para cada trabajo.
- Gratis conserva 1080p; Pro habilita 2K, 4K y máxima.
- El instalador no contiene una clave maestra reutilizable.
- Actualización automática y diagnóstico de Helper/FFmpeg/yt-dlp.

Salida de etapa: la misma suscripción funciona en web, Windows y macOS sin compartir códigos.

### Etapa 5 — Lanzamiento

- Cola de trabajos y workers separados del servidor web.
- Métricas de éxitos, fallos, reintentos, duración y costo.
- Alertas por tasa de error, disco, CPU, cola y pagos.
- Almacenamiento temporal con vencimiento y límites por cuenta.
- Soporte, términos, privacidad y procedimiento de reclamos.
- Lanzamiento gradual: 50, 250, 1.000 y luego 2.500 suscripciones.

## Criterios de “listo para vender”

- Ningún error técnico muestra sólo “falló”: informa qué ocurrió y qué puede hacer el usuario.
- Los reintentos no crean archivos duplicados ni cobran dos veces.
- Gratis nunca entrega más de 1080p desde la API.
- Pro se decide en el servidor y no mediante una bandera editable en el navegador.
- Los webhooks de pago son idempotentes.
- Un archivo vencido ya no puede descargarse.
- Hay métricas y alertas antes de aumentar publicidad.
- El flujo completo se prueba en Windows, macOS, iPhone y Android.
