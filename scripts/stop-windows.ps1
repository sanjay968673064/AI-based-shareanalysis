$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-DockerReady($DockerPath) {
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $DockerPath info *> $null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $oldErrorActionPreference
    return $exitCode -eq 0
}

Set-Location $Root

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    $commonDockerPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $commonDockerPath) {
        $docker = @{ Source = $commonDockerPath }
    }
}

if (-not $docker) {
    Write-Host "Docker is not available. Nothing was stopped." -ForegroundColor Yellow
    exit 0
}

Write-Step "Stopping AI Portfolio Advisor"
if (-not (Test-DockerReady -DockerPath $docker.Source)) {
    Write-Host "Docker Desktop is not running, so there is nothing to stop." -ForegroundColor Yellow
    exit 0
}

& $docker.Source compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] App stopped. Your saved database data remains in Docker." -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Docker Compose could not stop the app." -ForegroundColor Red
    exit $LASTEXITCODE
}
