<#
.SYNOPSIS
    Télécharge et extrait les sources des backends BLE C.

.DESCRIPTION
    BTstack  v1.8.2         → vendor/btstack-1.8.2/
    NimBLE   1.9.0          → vendor/mynewt-nimble-nimble_1_9_0_tag/

    WinRT n'a pas besoin de source vendor : les en-têtes Windows SDK
    sont déjà présents sur Windows 11 via le Windows SDK.

    BlueZ est exclu (Linux uniquement, non cross-compilable depuis Windows).

.NOTES
    Exécuter depuis le répertoire backends/ :
        cd src\Ada\backends
        .\fetch_vendors.ps1

    Prérequis : PowerShell 5+ ou PowerShell Core, accès internet.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Paramètres ─────────────────────────────────────────────────────────────
$VendorDir = Join-Path $PSScriptRoot "vendor"
$TmpDir    = Join-Path $env:TEMP "corelec_vendors"

$Downloads = @(
    @{
        Name     = "BTstack v1.8.2"
        Url      = "https://github.com/bluekitchen/btstack/archive/refs/tags/v1.8.2.zip"
        Zip      = "btstack-1.8.2.zip"
        # GitHub crée un dossier btstack-1.8.2 à l'intérieur du zip
        ZipRoot  = "btstack-1.8.2"
        Target   = "btstack-1.8.2"
    },
    @{
        Name     = "NimBLE 1.9.0"
        Url      = "https://github.com/apache/mynewt-nimble/archive/refs/tags/nimble_1_9_0_tag.zip"
        Zip      = "mynewt-nimble-1.9.0.zip"
        ZipRoot  = "mynewt-nimble-nimble_1_9_0_tag"
        Target   = "mynewt-nimble-nimble_1_9_0_tag"
    }
)

# ── Helpers ─────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

function Ensure-Dir([string]$path) {
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
}

# ── Main ─────────────────────────────────────────────────────────────────────
Ensure-Dir $VendorDir
Ensure-Dir $TmpDir

foreach ($pkg in $Downloads) {
    $targetPath = Join-Path $VendorDir $pkg.Target

    if (Test-Path $targetPath) {
        Write-Host "  [OK] $($pkg.Name) déjà présent → $targetPath" -ForegroundColor Green
        continue
    }

    Write-Step "Téléchargement : $($pkg.Name)"
    $zipPath = Join-Path $TmpDir $pkg.Zip

    if (-not (Test-Path $zipPath)) {
        Write-Host "  URL : $($pkg.Url)"
        Invoke-WebRequest -Uri $pkg.Url -OutFile $zipPath -UseBasicParsing
        Write-Host "  Téléchargé → $zipPath"
    } else {
        Write-Host "  Archive déjà en cache → $zipPath"
    }

    Write-Step "Extraction : $($pkg.Name)"
    $extractDir = Join-Path $TmpDir ("extract_" + $pkg.Target)
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $extractDir

    # Le zip GitHub crée un sous-dossier racine : déplacer directement dans vendor/
    $innerDir = Join-Path $extractDir $pkg.ZipRoot
    Move-Item -Path $innerDir -Destination $targetPath
    Remove-Item $extractDir -Recurse -Force

    Write-Host "  Extrait → $targetPath" -ForegroundColor Green
}

Write-Host "`n[DONE] Vendor sources prêts dans : $VendorDir" -ForegroundColor Yellow
Write-Host "  BTstack  : vendor\btstack-1.8.2\"
Write-Host "  NimBLE   : vendor\mynewt-nimble-nimble_1_9_0_tag\"
