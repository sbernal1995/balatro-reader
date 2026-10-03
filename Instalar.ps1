param(
    [string]$BalatroPath,
    [switch]$SkipModInstall
)
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$commit = 'e7c6db8a9ad88318f6e4128eefd6e61aafc94885'
$lovelyVersion = 'v0.10.0'
$smodsVersion = '26.1002.0'
$configPath = Join-Path $project 'config.local.json'
$deps = Join-Path $project '.deps'
$downloads = Join-Path $project '.downloads'
$upstream = Join-Path $deps 'balatrobot'
$engineVersion = 'v0.2.0'
$engineHash = 'F39CA0AF3C7559D497F88182753017640A8A000370960C67967F63C48B62B752'

function Find-Balatro {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($BalatroPath) { $candidates.Add($BalatroPath) }
    if (Test-Path -LiteralPath $configPath) {
        $saved = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        if ($saved.gamePath) { $candidates.Add($saved.gamePath) }
    }
    $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if ($steam) {
        $candidates.Add((Join-Path $steam 'steamapps\common\Balatro'))
        $libraries = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $libraries) {
            $content = Get-Content -LiteralPath $libraries -Raw
            foreach ($match in [regex]::Matches($content, '"path"\s+"([^"]+)"')) {
                $library = $match.Groups[1].Value.Replace('\\', '\')
                if (Test-Path -LiteralPath $library) {
                    $candidates.Add((Join-Path $library 'steamapps\common\Balatro'))
                }
            }
        }
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath ([System.IO.Path]::Combine($candidate, 'Balatro.exe'))) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'No se encontro Balatro. Ejecuta Instalar.cmd -BalatroPath "D:\SteamLibrary\steamapps\common\Balatro" con la ruta de tu juego.'
}

function Fetch-Zip($url, $name) {
    $archive = Join-Path $downloads "$name.zip"
    $expanded = Join-Path $downloads "$name-expanded"
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host "Descargando $name..."
        Invoke-WebRequest -Uri $url -OutFile $archive -UseBasicParsing
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
    return $expanded
}

function Copy-Mod($source, $target) {
    if (Test-Path -LiteralPath $target) {
        $backupRoot = Join-Path $project '.downloads\backups'
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $backup = Join-Path $backupRoot ((Split-Path $target -Leaf) + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff'))
        Copy-Item -LiteralPath $target -Destination $backup -Recurse
        Write-Host "Copia de respaldo: $backup"
    }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Instala uv primero: winget install --id astral-sh.uv --exact. Luego abre una nueva terminal o vuelve a ejecutar Instalar.cmd.'
}
if ((Get-Process -Name Balatro -ErrorAction SilentlyContinue) -and -not $SkipModInstall) {
    throw 'Cierra Balatro antes de instalar o actualizar los mods.'
}
$game = Find-Balatro
New-Item -ItemType Directory -Path $deps, $downloads -Force | Out-Null
$engineDir = Join-Path $project 'engine\target\release'
$enginePath = Join-Path $engineDir 'balatro-reader-engine.exe'
New-Item -ItemType Directory -Path $engineDir -Force | Out-Null
if (-not (Test-Path -LiteralPath $enginePath) -or (Get-FileHash -LiteralPath $enginePath -Algorithm SHA256).Hash -ne $engineHash) {
    Write-Host 'Descargando el motor de reglas de Balatro...'
    $engineDownload = Join-Path $downloads 'balatro-reader-engine-windows-x64.exe'
    Invoke-WebRequest -Uri "https://github.com/sbernal1995/balatro-reader/releases/download/$engineVersion/balatro-reader-engine-windows-x64.exe" -OutFile $engineDownload -UseBasicParsing
    if ((Get-FileHash -LiteralPath $engineDownload -Algorithm SHA256).Hash -ne $engineHash) {
        throw 'El motor descargado no coincide con la version verificada. Volve a descargar el proyecto.'
    }
    Copy-Item -LiteralPath $engineDownload -Destination $enginePath -Force
}

if (-not (Test-Path -LiteralPath (Join-Path $upstream 'pyproject.toml'))) {
    $extracted = Fetch-Zip "https://codeload.github.com/coder/balatrobot/zip/$commit" 'balatrobot-pinned'
    $source = Get-ChildItem -LiteralPath $extracted -Directory | Select-Object -First 1
    Copy-Item -LiteralPath $source.FullName -Destination $upstream -Recurse
}
$patch = Join-Path $project 'integrations\gamestate.lua'
Copy-Item -LiteralPath $patch -Destination (Join-Path $upstream 'src\lua\utils\gamestate.lua') -Force

if (-not (Test-Path -LiteralPath (Join-Path $project '.venv\Scripts\python.exe'))) {
    & uv venv --python 3.13 (Join-Path $project '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de Python 3.13.' }
}
$python = Join-Path $project '.venv\Scripts\python.exe'
& uv pip install --python $python $upstream -r (Join-Path $project 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }

if (-not $SkipModInstall) {
    $mods = Join-Path $env:APPDATA 'Balatro\Mods'
    $lovely = Fetch-Zip "https://github.com/ethangreen-dev/lovely-injector/releases/download/$lovelyVersion/lovely-x86_64-pc-windows-msvc.zip" 'lovely-pinned'
    $dll = Join-Path $game 'winmm.dll'
    if (Test-Path -LiteralPath $dll) {
        Copy-Item -LiteralPath $dll -Destination (Join-Path $downloads ('winmm-' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff') + '.dll.bak'))
    }
    Copy-Item -LiteralPath (Join-Path $lovely 'winmm.dll') -Destination $dll -Force
    $smods = Fetch-Zip "https://codeload.github.com/Steamodded/smods/zip/refs/tags/$smodsVersion" 'smods-pinned'
    $smodsSource = Get-ChildItem -LiteralPath $smods -Directory | Select-Object -First 1
    Copy-Mod $smodsSource.FullName (Join-Path $mods 'smods')
    $smodsConfig = Join-Path $mods 'smods\config.lua'
    $settings = [System.IO.File]::ReadAllText($smodsConfig)
    $settings = $settings.Replace('["achievements"] = 1', '["achievements"] = 2')
    [System.IO.File]::WriteAllText($smodsConfig, $settings)
    $modSource = Join-Path $downloads 'balatrobot-mod'
    New-Item -ItemType Directory -Path (Join-Path $modSource 'src') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $upstream 'balatrobot.lua'), (Join-Path $upstream 'balatrobot.json') -Destination $modSource -Force
    Copy-Item -LiteralPath (Join-Path $upstream 'src\lua') -Destination (Join-Path $modSource 'src') -Recurse -Force
    Copy-Mod $modSource (Join-Path $mods 'balatrobot')
}

@{gamePath=$game; apiPort=12346; panelPort=8765; upstreamCommit=$commit} |
    ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
Write-Host "Instalacion lista. Abri Iniciar.cmd. Juego: $game"
