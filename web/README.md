# PacheVideo Web

Installable mobile-first web interface for the PacheVideo processing API.

## Local development

1. Start the backend from the repository root:

```powershell
$env:PACHEVIDEO_DATA_DIR = "$PWD/server/data"
$env:PACHEVIDEO_PUBLIC_BASE_URL = "http://127.0.0.1:8080"
.\.venv-server\Scripts\python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8080
```

2. Start the web app:

```powershell
cd web
$env:PACHEVIDEO_API_URL = "http://127.0.0.1:8080"
npm run dev
```

The browser only submits and monitors jobs. yt-dlp, FFmpeg, temporary files, and cleanup all run on the backend.

## Production

Set `PACHEVIDEO_API_URL` in the web runtime to the HTTPS URL of the processing server. The backend can be deployed from `deploy/docker-compose.yml`; copy `deploy/.env.example` to `deploy/.env` and use a real API subdomain.

Before a public launch, configure `PACHEVIDEO_ALLOWED_HOSTS`, enforce an outbound firewall that blocks private networks, and place account/billing limits in front of job creation.

