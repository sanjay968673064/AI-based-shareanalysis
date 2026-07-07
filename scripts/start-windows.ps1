param(
    [switch]$NoBuild,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$AppUrl = "http://localhost:3000"
$ApiHealthUrl = "http://localhost:8000/health"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Fail($Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Get-DockerCommand {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        return $docker.Source
    }

    $commonDockerPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $commonDockerPath) {
        return $commonDockerPath
    }

    return $null
}

function Ensure-DockerInstalled {
    $dockerPath = Get-DockerCommand
    if ($dockerPath) {
        Write-Ok "Docker command found."
        return $dockerPath
    }

    Write-Warn "Docker Desktop is not installed or is not available in PATH."
    Write-Host "This app uses Docker Desktop so your friend does not need to install Node, Python, Postgres, or Redis manually."

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Fail "winget is not available on this computer."
        Write-Host "Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and run this file again."
        exit 1
    }

    $answer = Read-Host "Install Docker Desktop now with winget? This can take several minutes and may ask for admin permission. Type Y to continue"
    if ($answer -notin @("Y", "y", "Yes", "yes")) {
        Write-Host "No problem. Install Docker Desktop later, then double-click this file again."
        exit 1
    }

    Write-Step "Installing Docker Desktop"
    & winget install --exact --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Docker Desktop install did not finish successfully."
        exit $LASTEXITCODE
    }

    $env:Path = $env:Path + ";C:\Program Files\Docker\Docker\resources\bin"
    $dockerPath = Get-DockerCommand
    if (-not $dockerPath) {
        Write-Warn "Docker Desktop was installed, but Windows may need a sign-out, restart, or new terminal before docker is available."
        Write-Host "Restart the laptop if needed, then double-click this file again."
        exit 1
    }

    return $dockerPath
}

function Start-DockerDesktop {
    $dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktopPath) {
        Write-Step "Starting Docker Desktop"
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden | Out-Null
    }
}

function Test-DockerReady($DockerPath) {
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $DockerPath info *> $null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $oldErrorActionPreference
    return $exitCode -eq 0
}

function Wait-ForDocker($DockerPath) {
    Write-Step "Checking Docker Desktop"

    if (Test-DockerReady -DockerPath $DockerPath) {
        Write-Ok "Docker Desktop is running."
        return
    }

    Start-DockerDesktop

    Write-Host "Waiting for Docker Desktop to become ready. The first start can take a few minutes."
    for ($i = 1; $i -le 120; $i++) {
        if (Test-DockerReady -DockerPath $DockerPath) {
            Write-Ok "Docker Desktop is ready."
            return
        }
        Start-Sleep -Seconds 5
    }

    Write-Fail "Docker Desktop did not become ready."
    Write-Host "Open Docker Desktop manually and wait until it says it is running, then double-click this file again."
    exit 1
}

function Ensure-EnvFile {
    $envPath = Join-Path $Root ".env"
    $examplePath = Join-Path $Root ".env.example"

    if (Test-Path $envPath) {
        Write-Ok ".env file found."
        return
    }

    if (-not (Test-Path $examplePath)) {
        Write-Fail ".env.example is missing, so the app cannot create its default settings."
        exit 1
    }

    Copy-Item -LiteralPath $examplePath -Destination $envPath
    Write-Ok "Created .env from .env.example."
    Write-Host "Optional: edit .env later if you want to add Zerodha, OpenAI, Alpha Vantage, or Finnhub keys."
}

function Wait-ForUrl($Url, $Name, $Seconds) {
    Write-Step "Waiting for $Name"
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Ok "$Name is responding."
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 5
        }
    }
    Write-Warn "$Name did not respond within $Seconds seconds."
    return $false
}

if ($CheckOnly) {
    Write-Ok "Launcher script is readable."
    Write-Host "Project root: $Root"
    exit 0
}

Write-Host "AI Portfolio Advisor - one-click Windows launcher" -ForegroundColor White
Write-Host "This window will set up and start the local app, then open it in your browser."

Set-Location $Root
Ensure-EnvFile
$dockerPath = Ensure-DockerInstalled
Wait-ForDocker -DockerPath $dockerPath

Write-Step "Checking Docker Compose"
& $dockerPath compose version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Compose is not available. Update Docker Desktop and try again."
    exit 1
}
Write-Ok "Docker Compose is available."

Write-Step "Starting AI Portfolio Advisor"
if ($NoBuild) {
    & $dockerPath compose up -d
}
else {
    & $dockerPath compose up -d --build
}

if ($LASTEXITCODE -ne 0) {
    Write-Fail "The app did not start successfully."
    Write-Host ""
    Write-Host "Recent Docker logs:"
    & $dockerPath compose logs --tail=80
    exit $LASTEXITCODE
}

Wait-ForUrl -Url $ApiHealthUrl -Name "API" -Seconds 180 | Out-Null
Wait-ForUrl -Url $AppUrl -Name "web app" -Seconds 300 | Out-Null

Write-Step "Opening the app"
Start-Process $AppUrl
Write-Ok "AI Portfolio Advisor is running at $AppUrl"
Write-Host ""
Write-Host "To stop it later, double-click: Stop AI Portfolio Advisor.bat"
Write-Host "You can close this window after the browser opens."
