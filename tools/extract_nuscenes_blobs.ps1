# Extract nuScenes blob archives (*.tgz) into data/nuScenes (same layout as README).
# Run metadata first: tar -xzf datasets/v1.0-trainval_meta.tgz -C data/nuScenes
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File tools/extract_nuscenes_blobs.ps1
# Optional:
#   powershell -File tools/extract_nuscenes_blobs.ps1 -BlobTgz "datasets\v1.0-trainval01_blobs.tgz"

param(
    [string] $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string] $BlobTgz = ""
)

$dest = Join-Path $ProjectRoot "data\nuScenes"
$ds = Join-Path $ProjectRoot "datasets"

if (-not (Test-Path $dest)) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
}

function Test-FileExclusiveLock {
    param([string]$Path)
    try {
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None)
        $fs.Close()
        return $false
    } catch {
        return $true
    }
}

$candidates = @()
if ($BlobTgz -ne "" -and (Test-Path $BlobTgz)) {
    $candidates += (Resolve-Path $BlobTgz).Path
} elseif (Test-Path $ds) {
    $candidates += Get-ChildItem -Path $ds -Filter "*_blobs.tgz" | Sort-Object Name | ForEach-Object { $_.FullName }
}

if ($candidates.Count -eq 0) {
    Write-Error "No blob archives found under $ds (expected names like v1.0-trainval01_blobs.tgz)."
    exit 1
}

foreach ($arc in $candidates) {
    Write-Host "Extracting: $arc"
    Write-Host "Destination: $dest"
    if (-not (Test-Path $arc)) {
        Write-Warning "Skip missing file: $arc"
        continue
    }
    if (Test-FileExclusiveLock -Path $arc) {
        Write-Warning @"
Cannot open archive (file may be locked). Common fixes:
  - In OneDrive: right-click the .tgz -> Always keep on this device; wait until sync finishes.
  - Quit apps that might hold the file open; temporarily pause OneDrive sync.
  - Copy the .tgz to a local drive (e.g. C:\temp) and run this script with -BlobTgz path.
"@
        exit 2
    }
    & tar.exe -xzf $arc -C $dest
    if ($LASTEXITCODE -ne 0) {
        Write-Error "tar failed with exit code $LASTEXITCODE for $arc"
        exit $LASTEXITCODE
    }
}

Write-Host "Done. Expected layout under data\nuScenes: samples\, sweeps\, maps\, v1.0-trainval\"
Write-Host "Note: Full nuScenes trainval uses multiple blob parts (trainval01 ... trainval10). Extract all parts into the same folder."
