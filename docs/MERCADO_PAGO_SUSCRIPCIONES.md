# Mercado Pago: suscripción mensual de PacheVideo Pro

PacheVideo usa la integración de **Suscripciones** de Mercado Pago. El cobro no
usa un código de acceso ni un pago manual: Mercado Pago crea una suscripción
mensual y el servidor habilita Pro solo después de consultar su estado real.

## Antes de probar

1. Crear la aplicación **Suscripciones con integración** en Mercado Pago.
2. Mantenerla en modo **Pruebas**.
3. Crear un usuario comprador de prueba desde el panel de Mercado Pago.
4. Crear el proyecto de Supabase Auth y habilitar el acceso por enlace de email.
5. Guardar el Access Token de prueba únicamente como secreto del servidor.

Nunca subir tokens a Git, enviarlos por chat ni incorporarlos al frontend.

En Windows local, pegar el Access Token después de
`PACHEVIDEO_MP_ACCESS_TOKEN=` dentro de `server/.env` y reiniciar PacheVideo.
El iniciador local carga ese archivo automáticamente y Git lo ignora.

## Variables privadas del servidor

Configurar estas variables en el servidor de procesamiento:

```env
PACHEVIDEO_MP_ACCESS_TOKEN=APP_USR-...solo-en-el-servidor
PACHEVIDEO_MP_BACK_URL=https://pachevideo.com/app
PACHEVIDEO_MP_SUBSCRIPTION_AMOUNT=9999.99
PACHEVIDEO_MP_SUBSCRIPTION_CURRENCY=ARS
PACHEVIDEO_COOKIE_SECURE=true
PACHEVIDEO_SUPABASE_URL=https://tu-proyecto.supabase.co
PACHEVIDEO_SUPABASE_ANON_KEY=clave-publica-anon
```

`PACHEVIDEO_MP_BACK_URL` debe ser la URL pública definitiva de PacheVideo. No
usar una dirección temporal de desarrollo.

Durante una prueba local o por túnel de Cloudflare, la web envía automáticamente
su propia dirección de retorno al servidor. Esta excepción solo acepta
`localhost` y subdominios temporales `trycloudflare.com`; para producción sigue
siendo obligatorio configurar la URL estable del dominio.

## Webhook definitivo

Después de publicar el sitio, registrar esta dirección en la aplicación de
Mercado Pago:

```text
https://pachevideo.com/api/billing/mercadopago/webhook
```

Seleccionar las notificaciones de suscripción. Ante cada aviso, PacheVideo
consulta de nuevo el estado de la suscripción con Mercado Pago; solo el estado
`authorized` habilita Video Pro.

## Qué prueba hacer

1. Abrir PacheVideo en un navegador nuevo.
2. Elegir `Suscribirme por $9.999,99` e ingresar el email del comprador de prueba.
3. Completar el flujo de Mercado Pago con el comprador de prueba.
4. Confirmar que vuelve a PacheVideo con Video Pro activo.
5. Simular una cancelación o rechazo y comprobar que Pro vuelva a Gratis.

La suscripción queda vinculada al identificador autenticado de Supabase. El
cliente entra mediante un enlace enviado a su email, sin contraseña, y recupera
su plan Pro desde cualquier dispositivo.
