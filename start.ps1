[CmdletBinding()]
param(
    [string]$PostgresBin = '',
    [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$runtime = Join-Path $root '.local'
$database = 'avito_buddy_demo'
$dbPort = 55441
$apiPort = 5050
$webPort = 5177
$origin = "http://localhost:$webPort"
$pgData = Join-Path $runtime 'preview-pg'
$passwordFile = Join-Path $runtime 'preview-db-password'
$python = Join-Path $backend '.venv/Scripts/python.exe'
$services = @()
$startedDatabase = $false

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$(Split-Path $Program -Leaf) failed (exit $LASTEXITCODE)."
    }
}

function Assert-FreePort {
    param([int]$Port)
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is already in use. Close the existing preview or the program using that port."
    }
}

function Test-PreviewHealth {
    try {
        $health = Invoke-RestMethod -Uri "$origin/health" -TimeoutSec 2
        $page = Invoke-WebRequest -Uri $origin -TimeoutSec 2 -UseBasicParsing
        return $health.status -eq 'ok' -and $page.StatusCode -eq 200 -and
            $page.Content -match '<title>[^<]*AI-buddy[^<]*</title>'
    } catch {
        return $false
    }
}

function Get-PreviewCommandLine {
    param([int]$Port)
    $listener = Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$listener) { return '' }
    $process = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $listener.OwningProcess)
    return [string]$process.CommandLine
}

function Test-ExistingPreview {
    $api = Get-PreviewCommandLine $apiPort
    $web = Get-PreviewCommandLine $webPort
    $postgres = (Get-PreviewCommandLine $dbPort).Replace('/', '\')
    # The same preview can have been started from another copy of the repository.
    return ($api -like "*-m waitress --listen=127.0.0.1:$apiPort --call server.app:create_app*") -and
        ($web -like "*vite/bin/vite.js --config vite.integrated.config.ts*--port $webPort*") -and
        ($postgres -match '\bpostgres\.exe"?\s+-D\s+.*\\\.local\\preview-pg"?(?:\s|$)') -and
        (Test-PreviewHealth)
}

function Open-PreviewPage {
    if (!$OpenBrowser) { return }
    try {
        Start-Process -FilePath $origin
    } catch {
        Write-Warning "Could not open the browser. Open $origin manually."
    }
}

function Wait-ForPreview {
    param([System.Diagnostics.Process[]]$Processes)
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        foreach ($process in $Processes) {
            if ($process.HasExited) { throw 'A preview process stopped during startup.' }
        }
        if (Test-PreviewHealth) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "The preview did not become available at $origin."
}

$envKeys = @('PGPASSWORD', 'DATABASE_URL', 'PUBLIC_ORIGIN', 'PORTAL_PROTECT_LEGACY',
            'SESSION_COOKIE_SECURE', 'AI_MODE', 'BUDDY_AGENT_FACTORY', 'PYTHONPATH',
            'VITE_ENABLE_MSW', 'VITE_API_URL')
$savedEnv = @{}
foreach ($key in $envKeys) { $savedEnv[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }

try {
    if (Test-ExistingPreview) {
        Write-Host "AI Buddy is already running at $origin. Stop that preview before starting a different checkout."
        Open-PreviewPage
        return
    }
    Assert-FreePort $apiPort
    Assert-FreePort $webPort
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $nodeVersion = Invoke-Checked $node @('--version')
    if ([version]$nodeVersion.TrimStart('v') -lt [version]'20.0.0') { throw 'Install Node.js 20 or later.' }

    if (!$PostgresBin) {
        $pgCommand = Get-Command pg_ctl.exe -ErrorAction SilentlyContinue
        if ($pgCommand) {
            $PostgresBin = Split-Path $pgCommand.Source
        } else {
            $installRoot = Join-Path $env:ProgramFiles 'PostgreSQL'
            $install = Get-ChildItem $installRoot -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^\d+$' -and (Test-Path (Join-Path $_.FullName 'bin/pg_ctl.exe')) } |
                Sort-Object { [int]$_.Name } -Descending | Select-Object -First 1
            if (!$install) { throw 'Install PostgreSQL or pass -PostgresBin with the directory containing pg_ctl.exe.' }
            $PostgresBin = Join-Path $install.FullName 'bin'
        }
    }
    $pgCtl = Join-Path $PostgresBin 'pg_ctl.exe'
    if (!(Test-Path $pgCtl)) { throw "pg_ctl.exe was not found in $PostgresBin." }

    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    if (!(Test-Path $python)) {
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($py) {
            Invoke-Checked $py.Source @('-3.12', '-m', 'venv', (Join-Path $backend '.venv'))
        } else {
            Invoke-Checked (Get-Command python.exe -ErrorAction Stop).Source @('-m', 'venv', (Join-Path $backend '.venv'))
        }
    }
    $usesPython312 = Get-Content (Join-Path $backend '.venv/pyvenv.cfg') | Where-Object { $_ -match '^version\s*=\s*3\.12(\.|$)' }
    if (!$usesPython312) { throw 'Use a Python 3.12 virtual environment at backend/.venv.' }

    $requirements = @('server/requirements.txt', 'ai/pyproject.toml') | ForEach-Object { Join-Path $backend $_ }
    $pythonStamp = Join-Path $backend '.venv/avito-start-dependencies'
    $pythonHash = ((Get-FileHash -LiteralPath $requirements).Hash -join ':')
    if (!(Test-Path $pythonStamp) -or (Get-Content $pythonStamp -Raw).Trim() -ne $pythonHash) {
        Push-Location $backend
        try {
            Invoke-Checked $python @('-m', 'pip', 'install', '-r', 'server/requirements.txt', '-e', './ai')
            Set-Content -LiteralPath $pythonStamp -Value $pythonHash -Encoding ASCII
        } finally { Pop-Location }
    }
    $nodeStamp = Join-Path $frontend 'node_modules/.avito-start-dependencies'
    $nodeHash = (Get-FileHash (Join-Path $frontend 'package-lock.json')).Hash
    if (!(Test-Path (Join-Path $frontend 'node_modules/vite/bin/vite.js')) -or
        !(Test-Path $nodeStamp) -or (Get-Content $nodeStamp -Raw).Trim() -ne $nodeHash) {
        Push-Location $frontend
        try {
            Invoke-Checked $npm @('ci')
            Set-Content -LiteralPath $nodeStamp -Value $nodeHash -Encoding ASCII
        } finally { Pop-Location }
    }

    $clusterVersion = Join-Path $pgData 'PG_VERSION'
    if (!(Test-Path $clusterVersion)) {
        Assert-FreePort $dbPort
        if (!(Test-Path $passwordFile)) {
            [IO.File]::WriteAllText($passwordFile, [Guid]::NewGuid().ToString('N') + [Environment]::NewLine)
        }
        Invoke-Checked (Join-Path $PostgresBin 'initdb.exe') @('-D', $pgData, '-U', 'buddy',
            '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C', "--pwfile=$passwordFile")
    }
    $env:PGPASSWORD = [IO.File]::ReadAllText($passwordFile).Trim()
    $env:DATABASE_URL = "postgresql://buddy@127.0.0.1:$dbPort/$database"
    & $pgCtl status -D $pgData | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Assert-FreePort $dbPort
        Invoke-Checked $pgCtl @('start', '-D', $pgData, '-l', (Join-Path $runtime 'preview-postgres.log'),
            '-o', "-h 127.0.0.1 -p $dbPort", '-w')
        $startedDatabase = $true
    }
    $dbArgs = @('-w', '-h', '127.0.0.1', '-p', $dbPort, '-U', 'buddy')
    $existingDb = Invoke-Checked (Join-Path $PostgresBin 'psql.exe') ($dbArgs + @('-d', 'postgres', '-Atc',
        "SELECT datname FROM pg_database WHERE datname = 'avito_buddy_demo'"))
    if (!$existingDb) {
        Invoke-Checked (Join-Path $PostgresBin 'createdb.exe') ($dbArgs + $database)
    }

    $env:PUBLIC_ORIGIN = $origin
    $env:PORTAL_PROTECT_LEGACY = '1'
    $env:SESSION_COOKIE_SECURE = '0'
    $env:AI_MODE = 'demo'
    $env:BUDDY_AGENT_FACTORY = ''
    $env:PYTHONPATH = Join-Path $backend 'ai'
    Push-Location $backend
    try {
        Invoke-Checked $python @('-m', 'server.store', 'migrate')
        Invoke-Checked $python @('-m', 'server.store', 'seed')
    } finally { Pop-Location }

    $services += Start-Process -FilePath $python -WorkingDirectory $backend -ArgumentList @(
        '-m', 'waitress', "--listen=127.0.0.1:$apiPort", '--call', 'server.app:create_app'
    ) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'preview-api.log') `
        -RedirectStandardError (Join-Path $runtime 'preview-api-error.log')

    $env:VITE_ENABLE_MSW = 'false'
    $env:VITE_API_URL = ''
    $services += Start-Process -FilePath $node -WorkingDirectory $frontend -ArgumentList @(
        'node_modules/vite/bin/vite.js', '--config', 'vite.integrated.config.ts', '--host', '127.0.0.1',
        '--port', $webPort, '--strictPort'
    ) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'preview-web.log') `
        -RedirectStandardError (Join-Path $runtime 'preview-web-error.log')

    Wait-ForPreview $services
    Write-Host "AI Buddy is ready at $origin. Press Ctrl+C to stop."
    Open-PreviewPage
    for (;;) {
        Start-Sleep -Seconds 1
        if ($services | Where-Object { $_.HasExited }) { throw 'A preview process stopped.' }
    }
} catch {
    Write-Warning "Preview logs: $runtime"
    throw
} finally {
    foreach ($process in $services) {
        if (!$process.HasExited) { & taskkill.exe /PID $process.Id /T /F | Out-Null }
    }
    if ($startedDatabase) { & $pgCtl stop -D $pgData -m fast -w | Out-Null }
    foreach ($key in $envKeys) { [Environment]::SetEnvironmentVariable($key, $savedEnv[$key], 'Process') }
}
