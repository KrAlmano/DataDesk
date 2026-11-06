<#
.SYNOPSIS
Test a Windows installer in a disposable path, including frozen data workflows.
.DESCRIPTION
Refuses to run over an existing DataDesk installation. The installed application
must implement --smoke-test <report.json>. No source checkout or Python is used
to run the installed executable.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [string]$ReportDirectory
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'Bu kurulum testi Windows üzerinde çalıştırılmalıdır.' }
$InstallerPath = [IO.Path]::GetFullPath($InstallerPath)
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
    throw "Kurulum dosyası bulunamadı: $InstallerPath"
}
# Same stable identifier as DataDesk.iss; never modify a real installation.
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{9E9166A6-89CF-44F7-BAC6-29C01B85DA9D}_is1'
if (Test-Path -LiteralPath $uninstallKey) {
    throw 'Kurulum testi için temiz bir Windows kullanıcısı gerekir; mevcut DataDesk kurulumuna dokunulmadı.'
}
if ($ReportDirectory) {
    $ReportDirectory = [IO.Path]::GetFullPath($ReportDirectory)
    New-Item -ItemType Directory -Force -Path $ReportDirectory | Out-Null
}
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('DataDesk-install-test-' + [guid]::NewGuid().ToString('N'))
$installDirectory = Join-Path $testRoot 'Türkçe boşluklu DataDesk'
$documentsDirectory = Join-Path $testRoot 'Belgeler'
New-Item -ItemType Directory -Path $documentsDirectory -Force | Out-Null
$source = Join-Path $documentsDirectory '00123-kaynak.csv'
[IO.File]::WriteAllText($source, "Kod;Ad`r`n00123;İstanbul`r`n", [Text.UTF8Encoding]::new($true))
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$oldPlatform = $env:QT_QPA_PLATFORM
$installed = $false
try {
    $setupArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/TASKS=',
        ('/DIR="' + $installDirectory + '"'), ('/LOG="' + (Join-Path $testRoot 'install.log') + '"'))
    $installed = $true
    $setup = Start-Process -FilePath $InstallerPath -ArgumentList $setupArguments -Wait -PassThru
    if ($setup.ExitCode -ne 0) { throw "Kurulum başarısız: $($setup.ExitCode)" }
    $executable = Join-Path $installDirectory 'DataDesk.exe'
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw 'Kurulu DataDesk.exe bulunamadı.' }
    $shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'DataDesk.lnk'
    if (-not (Test-Path -LiteralPath $shortcut -PathType Leaf)) { throw 'Başlat menüsü kısayolu oluşturulmadı.' }
    $report = Join-Path $testRoot 'kurulu uygulama raporu.json'
    $env:QT_QPA_PLATFORM = 'offscreen'
    $smoke = Start-Process -FilePath $executable -ArgumentList @('--smoke-test', ('"' + $report + '"')) `
        -WorkingDirectory $documentsDirectory -Wait -PassThru
    if ($smoke.ExitCode -ne 0) { throw "Kurulu uygulama testi başarısız: $($smoke.ExitCode)" }
    if (-not (Test-Path -LiteralPath $report -PathType Leaf)) { throw 'Kurulu uygulama test raporu yazılmadı.' }
    $result = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($result.status -ne 'success') { throw 'Kurulu uygulama iş akışı doğrulanamadı.' }
    $uninstaller = Join-Path $installDirectory 'unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw 'Kaldırma programı bulunamadı.' }
    $remove = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
        ('/LOG="' + (Join-Path $testRoot 'uninstall.log') + '"')) -Wait -PassThru
    if ($remove.ExitCode -ne 0) { throw "Kaldırma başarısız: $($remove.ExitCode)" }
    $installed = $false
    if (Test-Path -LiteralPath $executable) { throw 'Kaldırma sonrasında uygulama dosyası kaldı.' }
    if (Test-Path -LiteralPath $shortcut) { throw 'Kaldırma sonrasında Başlat kısayolu kaldı.' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash) {
        throw 'Kaynak CSV dosyası kurulum/kaldırma sırasında değişti.'
    }
    Write-Output 'Windows kurulumu, kurulu uygulama akışı, kısayol, kaldırma ve kaynak koruması doğrulandı.'
}
finally {
    $env:QT_QPA_PLATFORM = $oldPlatform
    if ($ReportDirectory) {
        foreach ($name in @('install.log', 'uninstall.log', 'kurulu uygulama raporu.json')) {
            $file = Join-Path $testRoot $name
            if (Test-Path -LiteralPath $file) {
                Copy-Item -LiteralPath $file -Destination $ReportDirectory -Force
            }
        }
    }
    if ($installed) {
        $uninstaller = Join-Path $installDirectory 'unins000.exe'
        if (Test-Path -LiteralPath $uninstaller) {
            Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') `
                -Wait -ErrorAction Continue | Out-Null
        }
    }
    # testRoot is a fresh GUID path created by this script, never a supplied path.
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction Continue
}
