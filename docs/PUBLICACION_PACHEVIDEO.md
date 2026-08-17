# Publicación de PacheVideo

## Arquitectura de producción

| Dirección | Servicio | Función |
| --- | --- | --- |
| `pachevideo.com` | Cloudflare Pages | Página pública y aplicación web instalable. |
| `www.pachevideo.com` | Cloudflare Pages | Redirección a `pachevideo.com`. |
| `api.pachevideo.com` | VPS con Docker y Caddy | API, yt-dlp, FFmpeg, cola y archivos temporales. |
| `auth.pachevideo.com` | Mailgun | Dominio de envío de los correos de acceso. No aloja una web. |

## Única intervención del titular

1. Crear una cuenta en Cloudflare y agregar `pachevideo.com`.
2. Copiar los dos *nameservers* que muestra Cloudflare en GoDaddy. No eliminar los registros de Mailgun.
3. Contratar un VPS Linux con IP pública. Para el lanzamiento inicial: 8 vCPU, 16 GB RAM y SSD/NVMe.
4. Dar acceso de administrador al VPS por una llave SSH o ejecutar los comandos que se indiquen en la consola. Nunca enviar contraseñas, tokens de Mercado Pago ni claves SMTP por chat.
5. Cargar las credenciales privadas directamente en el archivo `.env` del servidor y en los paneles de Supabase/Mercado Pago.

## DNS final

- `@` y `www`: los configura Cloudflare Pages cuando se publique la web.
- `api`: registro `A` a la IP pública del VPS. Debe estar como **DNS only** para que Caddy pueda emitir el certificado HTTPS inicialmente.
- `auth` y sus subregistros: conservar exactamente los registros SPF, DKIM y MX que dio Mailgun. No crear un `A` o `CNAME` para `auth`.

## Backend

En el VPS, copiar `deploy/.env.example` como `deploy/.env`, completar las variables y ejecutar:

```bash
cd deploy
docker compose up -d --build
```

El estado se comprueba en `https://api.pachevideo.com/api/health`.

## Seguridad antes de campaña

- Activar Cloudflare WAF y Turnstile en el formulario de creación de descargas.
- Mantener el límite global `PACHEVIDEO_MAX_ACTIVE_JOBS` y el límite por IP.
- Usar un firewall que permita al VPS solo puertos 22, 80 y 443.
- Dejar los archivos temporales con vencimiento corto; PacheVideo ya los limpia automáticamente.
- Configurar la URL de webhook de Mercado Pago solo cuando `api.pachevideo.com` responda por HTTPS.
