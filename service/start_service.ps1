$ErrorActionPreference = "Stop"

$ServiceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackDir = Join-Path $ServiceDir "Back"
$FrontDir = Join-Path $ServiceDir "Front"

if (-not (Test-Path (Join-Path $BackDir "main.py"))) {
    Write-Host "Back 폴더에서 main.py를 찾을 수 없습니다." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $FrontDir "package.json"))) {
    Write-Host "Front 폴더에서 package.json을 찾을 수 없습니다." -ForegroundColor Red
    exit 1
}

Write-Host "전라남도 응급의료 지원 시스템을 실행합니다." -ForegroundColor Cyan
Write-Host "백엔드: http://localhost:8000"
Write-Host "프론트: http://localhost:5173"
Write-Host ""

$BackendCommand = @"
Set-Location -LiteralPath '$BackDir'
Write-Host '백엔드 서버 실행 중... http://localhost:8000' -ForegroundColor Green
python main.py
Read-Host '백엔드 서버가 종료되었습니다. 창을 닫으려면 Enter를 누르세요'
"@

$FrontendCommand = @"
Set-Location -LiteralPath '$FrontDir'
Write-Host '프론트 서버 실행 중... http://localhost:5173' -ForegroundColor Green
npm run dev
Read-Host '프론트 서버가 종료되었습니다. 창을 닫으려면 Enter를 누르세요'
"@

Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand
Start-Sleep -Seconds 2
Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand

Write-Host "실행 요청을 보냈습니다. 열린 PowerShell 창 2개를 확인하세요." -ForegroundColor Green
Write-Host "브라우저에서 http://localhost:5173 로 접속하면 됩니다."
