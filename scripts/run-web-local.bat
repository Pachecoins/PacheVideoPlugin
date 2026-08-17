@echo off
setlocal
for %%I in ("%~dp0..") do set "PACHEVIDEO_ROOT=%%~fI"
cd /d "%PACHEVIDEO_ROOT%\web"
npm run build
if errorlevel 1 exit /b 1
npm run start -- --host 0.0.0.0
