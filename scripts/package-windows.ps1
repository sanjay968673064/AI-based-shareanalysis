$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$DistDir = Join-Path $Root "dist"
$StageDir = Join-Path $DistDir "AI-Portfolio-Advisor"
$ZipPath = Join-Path $DistDir "AI-Portfolio-Advisor-Windows.zip"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-ChildPath($Child, $Parent) {
    $parentResolved = [System.IO.Path]::GetFullPath($Parent)
    $childResolved = [System.IO.Path]::GetFullPath($Child)
    if (-not $childResolved.StartsWith($parentResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to use path outside expected folder: $Child"
    }
}

Set-Location $Root

Write-Step "Preparing package folder"
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
Assert-ChildPath -Child $StageDir -Parent $DistDir
Assert-ChildPath -Child $ZipPath -Parent $DistDir

if (Test-Path $StageDir) {
    Remove-Item -LiteralPath $StageDir -Recurse -Force
}
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Force -Path $StageDir | Out-Null

Write-Step "Copying app files"
$excludeDirs = @(".git", ".next", "node_modules", "dist")
$excludeFiles = @(".env", "*.log")

robocopy $Root $StageDir /E /XD $excludeDirs /XF $excludeFiles /NFL /NDL /NJH /NJS /NP | Out-Null
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -gt 7) {
    throw "Robocopy failed with exit code $robocopyExit"
}

Write-Step "Creating zip"
Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $ZipPath -Force
Remove-Item -LiteralPath $StageDir -Recurse -Force

Write-Host ""
Write-Host "[OK] Package created:" -ForegroundColor Green
Write-Host $ZipPath
Write-Host ""
Write-Host "Send that zip file to your friend. They should extract it, then double-click Start AI Portfolio Advisor.bat."
