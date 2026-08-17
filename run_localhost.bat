@echo off
setlocal
set "PACHEVIDEO_ROOT=%~dp0"

if not exist "%PACHEVIDEO_ROOT%.venv-server\Scripts\python.exe" (
  echo Falta el entorno del servidor en .venv-server.
  pause
  exit /b 1
)

if not exist "%PACHEVIDEO_ROOT%web\node_modules" (
  echo Faltan las dependencias de la web en web\node_modules.
  pause
  exit /b 1
)

start "PacheVideo API" cmd /k call "%PACHEVIDEO_ROOT%scripts\run-api-local.bat"
start "PacheVideo Web" cmd /k call "%PACHEVIDEO_ROOT%scripts\run-web-local.bat"

ping 127.0.0.1 -n 4 >nul
start "" "http://localhost:3000/app"

echo PacheVideo se esta iniciando en http://localhost:3000/app
echo Deja abiertas las dos ventanas mientras lo uses en modo local.

