<#
.SYNOPSIS
Build the Windows application and its per-user Inno Setup installer.
.EXAMPLE
pwsh -File packaging/windows/Build-Installer.ps1
.EXAMPLE
pwsh -File packaging/windows/Build-Installer.ps1 -SkipBundle -IsccPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
#>
[CmdletBinding()]
param(
    [string]$OutputDirectory = 'dist',
    [string]$IsccPath,
    [switch]$SkipBundle
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT') {
    throw 'Windows kurulum paketi Windows üzerinde derlenmelidir.'
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if (-not [IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot $OutputDirectory
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)

function Find-InnoCompiler {
    param([string]$ExplicitPath)
    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "Inno Setup derleyicisi bulunamadı: $ExplicitPath"
        }
        return [IO.Path]::GetFullPath($ExplicitPath)
    }
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($release in @('Inno Setup 7', 'Inno Setup 6')) {
        foreach ($folder in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
            if ($folder) {
                $candidate = Join-Path $folder (Join-Path $release 'ISCC.exe')
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
            }
        }
    }
    throw 'Inno Setup 6.4+ bulunamadı. https://jrsoftware.org/isdl.php adresinden kurun veya -IsccPath ile ISCC.exe yolunu belirtin.'
}

$compiler = Find-InnoCompiler $IsccPath
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv bulunamadı. Geliştirici kurulumu için docs/WINDOWS.md dosyasına bakın.'
}

Push-Location $projectRoot
try {
    if (-not $SkipBundle) {
        & uv run --extra build python tools/build_app.py --platform windows --output-dir $OutputDirectory
        if ($LASTEXITCODE -ne 0) { throw "DataDesk uygulama derlemesi başarısız oldu (kod $LASTEXITCODE)." }
    }
    $sourceDirectory = Join-Path $OutputDirectory 'DataDesk'
    $executable = Join-Path $sourceDirectory 'DataDesk.exe'
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Paketlenecek uygulama bulunamadı: $executable"
    }
    $icon = Join-Path $projectRoot 'build\icons\datadesk.ico'
    if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) {
        throw 'Windows simgesi bulunamadı. Önce tools/build_app.py ile uygulamayı derleyin.'
    }
    $versionLines = & uv run --extra build python -c 'from datadesk import __version__; print(__version__)'
    if ($LASTEXITCODE -ne 0) { throw 'DataDesk sürüm bilgisi okunamadı.' }
    $version = ($versionLines | Select-Object -Last 1).Trim()
    if ($version -notmatch '^\d+\.\d+\.\d+(\.\d+)?$') {
        throw "Windows sürüm bilgisi geçersiz: $version"
    }
    $installerDirectory = Join-Path $OutputDirectory 'installers'
    New-Item -ItemType Directory -Force -Path $installerDirectory | Out-Null
    & $compiler '/Qp' "/DAppVersion=$version" "/DAppSourceDir=$sourceDirectory" `
        "/DInstallerOutputDir=$installerDirectory" (Join-Path $PSScriptRoot 'DataDesk.iss')
    if ($LASTEXITCODE -ne 0) { throw "Windows kurulum paketi oluşturulamadı (kod $LASTEXITCODE)." }
    $installer = Join-Path $installerDirectory "DataDesk-$version-windows-x64-setup.exe"
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
        throw "Derleme tamamlandı ancak kurulum dosyası bulunamadı: $installer"
    }
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    $hashFile = $installer + '.sha256'
    [IO.File]::WriteAllText($hashFile, ($hash + '  ' + [IO.Path]::GetFileName($installer) + "`n"), [Text.Encoding]::ASCII)
    Write-Output $installer
    Write-Output $hashFile
}
finally {
    Pop-Location
}
