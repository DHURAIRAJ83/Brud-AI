# Tamil AI Assistant — One-Click Windows Setup
# Run from h:\AI_LLM\Tamil_AI

Write-Host "🤖 Tamil AI Assistant Setup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# ── Backend ───────────────────────────────────────────────────────────────────
Write-Host "`n[1/4] Setting up Python virtual environment..." -ForegroundColor Yellow
Set-Location backend

if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "  ✅ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  Virtual environment already exists" -ForegroundColor Gray
}

Write-Host "`n[2/4] Installing Python dependencies..." -ForegroundColor Yellow
& ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet
Write-Host "  ✅ Dependencies installed" -ForegroundColor Green

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✅ .env file created from template" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  .env already exists, skipping" -ForegroundColor Gray
}

# Create uploads dir
if (-not (Test-Path "uploads")) {
    New-Item -ItemType Directory -Name "uploads" | Out-Null
    Write-Host "  ✅ uploads/ directory created" -ForegroundColor Green
}

# ── Frontend ──────────────────────────────────────────────────────────────────
Write-Host "`n[3/4] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location ..\frontend
npm install --silent
Write-Host "  ✅ Node modules installed" -ForegroundColor Green

Set-Location ..

# ── Instructions ─────────────────────────────────────────────────────────────
Write-Host "`n[4/4] Setup complete! 🎉" -ForegroundColor Green
Write-Host "`n📋 Next steps:" -ForegroundColor Cyan
Write-Host "  1. Install Ollama: https://ollama.com/download"
Write-Host "  2. Pull a model:   ollama pull mistral"
Write-Host "  3. Start Ollama:   ollama serve"
Write-Host ""
Write-Host "  In Terminal 1 (Backend):"
Write-Host "    cd backend"
Write-Host "    .\venv\Scripts\activate"
Write-Host "    python main.py"
Write-Host ""
Write-Host "  In Terminal 2 (Frontend):"
Write-Host "    cd frontend"
Write-Host "    npm start"
Write-Host ""
Write-Host "  Open: http://localhost:3000" -ForegroundColor Cyan
Write-Host "  API:  http://localhost:8000/docs" -ForegroundColor Cyan
