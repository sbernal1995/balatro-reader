$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$configPath = Join-Path $project 'config.local.json'
$python = Join-Path $project '.venv\Scripts\python.exe'
$cli = Join-Path $project '.venv\Scripts\balatrobot.exe'
$engine = Join-Path $project 'engine\target\release\balatro-reader-engine.exe'
if (-not (Test-Path -LiteralPath $configPath) -or -not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $engine)) {
    Write-Host 'Primero ejecuta Instalar.cmd. Consulta INSTALACION.md.'
    exit 1
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$game = $config.gamePath
$executable = Join-Path $game 'Balatro.exe'
$lovely = Join-Path $game 'winmm.dll'
if (-not (Test-Path -LiteralPath $executable) -or -not (Test-Path -LiteralPath $lovely)) {
    throw 'No se encontro Balatro o Lovely. Ejecuta Instalar.cmd nuevamente.'
}
if (-not (Get-NetTCPConnection -LocalPort 12346 -State Listen -ErrorAction SilentlyContinue)) {
    if (Get-Process -Name Balatro -ErrorAction SilentlyContinue) {
        throw 'Balatro esta abierto sin la API. Cerralo y vuelve a ejecutar Iniciar.cmd.'
    }
    Start-Process -FilePath $cli -ArgumentList @('serve', '--port', '12346', '--audio', '--gamespeed', '1', '--love-path', ('"' + $executable + '"'), '--lovely-path', ('"' + $lovely + '"')) -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput "$project\game.log" -RedirectStandardError "$project\game-error.log"
}
if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $python -ArgumentList ('"' + (Join-Path $project 'reader.py') + '"') -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput "$project\reader.log" -RedirectStandardError "$project\reader-error.log"
}
Start-Process 'http://127.0.0.1:8765'
