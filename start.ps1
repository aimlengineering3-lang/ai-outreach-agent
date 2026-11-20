# start.ps1 - launches the API and the frontend, each in its own PowerShell
# window, so you don't have to open two terminals by hand every time.
#
# Run from the project root (C:\Projects\AI-Outreach Agent):
#   .\start.ps1
#
# This is just a convenience script, not part of the app - safe to delete
# any time, and safe to re-run (it just opens two fresh windows).

$root = $PSScriptRoot

Write-Host "Starting API (uvicorn) in its own window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$root'; & '$root\.venv\Scripts\python.exe' -m uvicorn api.main:app --reload --port 8000"
)

Start-Sleep -Seconds 1

Write-Host "Starting frontend (npm run dev) in its own window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$root\frontend'; npm run dev"
)

Write-Host ""
Write-Host "Both started. Give the frontend a few seconds to compile, then open:" -ForegroundColor Green
Write-Host "  http://localhost:3000" -ForegroundColor Yellow
Write-Host "(not 127.0.0.1 - the API's CORS only allows localhost)" -ForegroundColor DarkGray