# One command: backend on :8000 + Vite on :5173. Open http://localhost:5173
$root = Join-Path $PSScriptRoot ".."
$back = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory (Join-Path $root "backend") `
  -FilePath (Join-Path $root ".venv\Scripts\python.exe") `
  -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--reload"
try { Set-Location (Join-Path $root "frontend"); npm run dev } finally { Stop-Process -Id $back.Id -ErrorAction SilentlyContinue }
