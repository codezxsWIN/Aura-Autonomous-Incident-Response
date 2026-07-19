$root = "C:\Users\amitdamle\Downloads\hackathon"
$py = Join-Path $root ".venv\Scripts\python.exe"
$log = Join-Path $root ".aura-server.log"
$err = Join-Path $root ".aura-server.err.log"
$proc = Start-Process -FilePath $py `
  -ArgumentList '-m', 'uvicorn', 'app.main:app', '--app-dir', "$root\backend", '--host', '127.0.0.1', '--port', '8000' `
  -WorkingDirectory $root `
  -WindowStyle Hidden `
  -RedirectStandardOutput $log `
  -RedirectStandardError $err `
  -PassThru
Write-Output "started detached uvicorn PID $($proc.Id)"
