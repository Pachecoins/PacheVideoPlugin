@echo off
setlocal
for %%I in ("%~dp0..") do set "PACHEVIDEO_ROOT=%%~fI"
set "PACHEVIDEO_DATA_DIR=%PACHEVIDEO_ROOT%\server\data"
set "PACHEVIDEO_PUBLIC_BASE_URL=http://127.0.0.1:8080"
set "PACHEVIDEO_SUPABASE_URL=https://mwxoemxyeqtjcaxgtoub.supabase.co"
set "PACHEVIDEO_SUPABASE_ANON_KEY=sb_publishable_agoTpAsjmtyooDdXZzhNFQ_Sdxj8Oh-"
if exist "%PACHEVIDEO_ROOT%\server\.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%PACHEVIDEO_ROOT%\server\.env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)
cd /d "%PACHEVIDEO_ROOT%\server"
"%PACHEVIDEO_ROOT%\.venv-server\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8080
