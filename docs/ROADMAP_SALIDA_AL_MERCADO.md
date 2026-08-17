# Roadmap de salida al mercado de PacheVideo

## Objetivo del pack

Vender **una sola cuenta PacheVideo** con tres formas de acceso:

1. **PacheVideo Web:** landing pública y aplicación en `/app`.
2. **PacheVideo Mobile:** la misma aplicación web instalada como PWA desde Safari o Chrome. El celular no ejecuta FFmpeg; solamente crea el trabajo, consulta el progreso y descarga el resultado producido por el servidor.
3. **PacheVideo Desktop:** instalador Windows. El procesamiento puede ser local para reducir el costo del servidor, pero la licencia, el plan y el soporte deben depender de la misma cuenta PacheVideo.

No hace falta publicar una aplicación nativa en App Store o Google Play para la primera salida. La PWA permite validar el mercado primero. Android puede empaquetarse más adelante como Trusted Web Activity y iOS puede evaluarse cuando justifique la membresía y la revisión de Apple.

## Estado actual

| Componente | Estado | Falta para vender públicamente |
|---|---|---|
| Landing comercial | Funcional | Dominio, textos legales, analítica y checkout real |
| Aplicación web | Funcional en beta/LAN | Servidor público, cuentas, créditos, pagos y protección antiabuso |
| Experiencia móvil | Funcional en navegador | Completar PWA: HTTPS, registro del service worker, iconos 192/512, instalación guiada y pruebas iOS/Android |
| Servidor de procesamiento | Funcional para beta | PostgreSQL, cola durable, almacenamiento de objetos, monitoreo y copias de seguridad |
| Instalador Windows | Generable | Firma de código, actualización, licenciamiento y página de descarga |
| Instalador macOS | Generable para pruebas | Sin firma/notarización no es una experiencia apta para público general |
| Planes y créditos | Diseñados | Implementación y panel administrativo |
| Mercado Pago | Diseñado | Cuenta vendedora, credenciales, checkout y webhooks |

## Oferta comercial recomendada

### Gratis

- Audio sin consumir créditos, con límites técnicos.
- 5 descargas de video hasta 1080p por cuenta verificada.
- Un trabajo simultáneo.
- Publicidad o patrocinio claramente separado del botón de descarga.

### Pro — precio inicial ARS 9.999,99 por mes

- Video sin créditos mensuales, sujeto a uso razonable.
- Listas Pro de hasta 20 enlaces, con un archivo y progreso por cada enlace.
- Dos trabajos simultáneos y cola prioritaria.
- Sin anuncios.
- Acceso a PacheVideo Desktop para Windows.
- Precio configurable desde administración, sin publicar otra versión.

### Venta beta inmediata

Mientras se integra el checkout, se puede abrir una **Beta Fundadores** limitada:

- Crear un plan mensual desde Mercado Pago y compartir el enlace de suscripción.
- Aprobar manualmente cada cliente y enviarle el instalador desde una página privada.
- Registrar cliente, fecha, pago, versión instalada y soporte en una tabla administrativa.
- Limitar la beta a un grupo pequeño y comunicar que todavía no hay activación automática.
- Pasar a webhooks y licencias automáticas antes de hacer publicidad masiva.

## Checklist de lanzamiento

### Etapa 1 — Marca, propiedad y reglas

- [ ] Registrar dominio y reservar los usuarios sociales de PacheVideo.
- [ ] Definir la persona o entidad que factura y aparece como vendedor.
- [ ] Publicar Condiciones de servicio, Privacidad, Cookies y Política de contenido autorizado.
- [ ] Incluir un canal de denuncias, retiro de contenido y soporte.
- [ ] Revisar con asesoría legal las fuentes permitidas y las condiciones de cada plataforma compatible.
- [ ] Publicar límites de duración, tamaño, concurrencia, retención y uso razonable.
- [ ] No prometer compatibilidad universal ni descargas de contenido sin autorización.

**Puerta de salida:** dominio, identidad comercial y textos legales visibles.

### Etapa 2 — Cuenta, créditos y administración

- [ ] Registro e inicio de sesión con email verificado.
- [ ] Recuperación y eliminación de cuenta.
- [ ] Crear `users`, `subscriptions`, `credit_ledger`, `jobs` y `webhook_events` en PostgreSQL.
- [x] Otorgar 5 créditos de video una única vez por cuenta verificada y controlar el cupo en el servidor.
- [ ] Reservar el crédito al encolar; consumir al completar; devolver al fallar.
- [ ] Aplicar límites a audio aunque cueste cero créditos.
- [ ] Crear panel mínimo para buscar usuarios, trabajos, créditos, pagos y errores.
- [ ] Registrar acciones administrativas en auditoría.

**Puerta de salida:** dos cuentas distintas nunca comparten saldo ni trabajos y todos los movimientos son auditables.

### Etapa 3 — Cobros

- [ ] Crear cuenta vendedora y aplicación de Mercado Pago.
- [ ] Crear el plan Pro mensual con precio configurable.
- [ ] Implementar checkout desde la landing y desde la cuenta.
- [ ] Validar firma y origen de los webhooks.
- [ ] Procesar eventos de forma idempotente.
- [ ] Activar Pro únicamente después de confirmar el estado en el backend.
- [ ] Implementar cancelación, vencimiento, reintentos y devolución.
- [ ] Probar compra, rechazo, cancelación y webhook duplicado con credenciales de prueba.
- [ ] Emitir confirmación de pago y acceso.

**Puerta de salida:** ningún regreso del navegador desde el checkout puede activar Pro por sí solo.

### Etapa 4 — Servidor público seguro

- [ ] Publicar `app.pachevideo.com` y `api.pachevideo.com` con HTTPS.
- [ ] Ejecutar API y workers en contenedores separados.
- [ ] Agregar cola durable con prioridad Gratis/Pro.
- [ ] Migrar trabajos, usuarios y créditos a PostgreSQL.
- [ ] Subir resultados a almacenamiento de objetos y entregar URLs firmadas temporales.
- [ ] Borrar archivos automáticamente después del vencimiento.
- [ ] Bloquear redes privadas y destinos internos desde el downloader para evitar SSRF.
- [ ] Mantener allowlist explícita de fuentes compatibles.
- [ ] Aplicar rate limits por usuario, IP y plan.
- [ ] Establecer límites globales de workers y gasto.
- [ ] Configurar backups, métricas, logs, alertas y un botón de emergencia para pausar trabajos nuevos.
- [ ] Medir costo, tiempo y tasa de error por trabajo.

**Puerta de salida:** una caída de un worker no pierde el trabajo ni derriba la web.

### Etapa 5 — Web y PWA para celular

- [x] Separar landing `/` y aplicación `/app`.
- [x] Crear manifest y diseño responsive inicial.
- [ ] Cambiar el `start_url` de la PWA a `/app`.
- [ ] Generar iconos maskable de 192×192 y 512×512.
- [ ] Registrar el service worker y mostrar una pantalla offline comprensible.
- [ ] Agregar botón “Instalar PacheVideo” donde el navegador lo permita.
- [ ] Mostrar instrucciones específicas de “Agregar a inicio” en Safari para iPhone.
- [ ] Probar instalación, login, carga, espera y descarga en iPhone y Android reales.
- [ ] Conservar el trabajo en el servidor aunque el usuario cierre la pantalla.
- [ ] Enviar notificación o email cuando termine un trabajo largo.
- [ ] Verificar que ningún archivo se procese en el teléfono.

**Puerta de salida:** un usuario puede empezar en computadora, continuar en celular y ver el mismo trabajo con su cuenta.

### Etapa 6 — PacheVideo Desktop para Windows

- [x] Generar un instalador completo con aplicación, helper y desinstalador.
- [x] Quitar del producto comercial cualquier dependencia o texto de UXP/Premiere.
- [ ] Agregar inicio de sesión y validación de la licencia Pro.
- [ ] Definir gracia offline; recomendación inicial: siete días.
- [ ] Firmar ejecutables e instalador con una identidad consistente.
- [ ] Agregar comprobación de actualizaciones firmadas.
- [ ] Publicar versión, fecha, requisitos, SHA-256 y notas de cambios.
- [ ] Crear descarga privada para Beta Fundadores y pública después de firmar.
- [ ] Probar instalación limpia, actualización, reparación y desinstalación en Windows 10 y 11.
- [ ] Confirmar que antivirus y SmartScreen no detectan comportamiento no deseado.

**Puerta de salida:** instalar, actualizar y desinstalar no pierde preferencias ni deja procesos huérfanos.

### Etapa 7 — Calidad y capacidad

- [ ] Ejecutar pruebas automáticas del frontend, API, créditos y webhooks en cada release.
- [ ] Probar enlaces válidos, privados, eliminados, largos y restringidos.
- [ ] Probar caída de FFmpeg, yt-dlp, disco, red, cola y almacenamiento.
- [ ] Hacer una beta cerrada con 20–50 usuarios reales.
- [ ] Registrar conversión, errores por fuente, espera y costo por descarga.
- [ ] Hacer prueba de carga con trabajos cortos, medios y largos.
- [ ] Definir objetivo de disponibilidad y tiempo máximo de cola para Pro.
- [ ] Preparar rollback de web, API, worker e instalador.
- [ ] Mantener un canal de soporte y respuesta a incidentes.

**Puerta de salida:** siete días de beta estable y costos medidos antes de comprar tráfico.

### Etapa 8 — Venta y adquisición

- [ ] Conectar analítica respetuosa de privacidad al embudo landing → registro → primer video → Pro.
- [ ] Publicar demostración corta y capturas reales del producto.
- [ ] Preparar anuncios con una sola promesa verificable.
- [ ] Crear onboarding y email de bienvenida.
- [ ] Crear programa de referidos o código de Beta Fundadores.
- [ ] Empezar con anuncios de presupuesto limitado y aumentar solamente si la conversión cubre infraestructura y soporte.
- [ ] Revisar mensualmente precio, costo por descarga, churn y margen.

## Orden de ejecución sugerido

### Sprint 1 — Beta cobrable

1. Dominio y textos legales.
2. Servidor público con HTTPS y límites estrictos.
3. Plan de Mercado Pago sin integración.
4. Página privada para descargar Windows.
5. 20 usuarios de Beta Fundadores y soporte manual.

### Sprint 2 — Producto comercial automatizado

1. Cuentas y email verificado.
2. Créditos auditables.
3. Suscripción Mercado Pago con webhooks.
4. PWA instalable completa.
5. Licencia y actualización de Windows.

### Sprint 3 — Escala

1. Cola durable y workers separados.
2. Almacenamiento de objetos y URLs temporales.
3. Prioridad Pro, monitoreo y presupuestos.
4. Pruebas de carga y adquisición pagada gradual.

### Sprint 4 — Tiendas, solamente si los datos lo justifican

1. Android con Trusted Web Activity y prueba cerrada en Google Play.
2. Evaluar iOS/App Store y membresía Apple Developer.
3. Evaluar Microsoft Store o mantener distribución directa firmada.

## Criterio de “listo para vender”

PacheVideo puede aceptar público general cuando:

- El usuario puede registrarse, pagar, cancelar y recuperar su cuenta sin intervención manual.
- Los créditos y pagos son auditables e idempotentes.
- La infraestructura es pública, segura, monitoreada y recuperable.
- Los archivos vencen y se eliminan automáticamente.
- Hay límites y un apagado de emergencia para controlar costos.
- El instalador está firmado, versionado y tiene actualización segura.
- La PWA fue probada en iPhone y Android reales.
- Hay soporte, términos, privacidad y un proceso de denuncias.

## Referencias oficiales

- [Apple: convertir un sitio en web app desde Safari](https://support.apple.com/en-ie/guide/iphone/iphea86e5236/ios)
- [Apple Developer Program y costos](https://developer.apple.com/support/compare-memberships/)
- [Android: Trusted Web Activities](https://developer.android.com/develop/ui/views/layout/webapps/trusted-web-activities)
- [Microsoft: reputación SmartScreen](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [Mercado Pago: planes de suscripción](https://www.mercadopago.com.ar/developers/es/docs/subscription-plans/overview)
- [Mercado Pago: Webhooks](https://www.mercadopago.com.ar/developers/es/docs/your-integrations/notifications/webhooks)
