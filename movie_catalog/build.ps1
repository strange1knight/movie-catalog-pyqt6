param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$env:PATH = (($env:PATH -split ";") | Where-Object { $_ -notmatch "[\\/]poppler[\\/]" }) -join ";"

& $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name MovieCatalog `
    --add-data "movie_catalog/main_window.ui;movie_catalog" `
    --add-data "movie_catalog/movie_dialog.ui;movie_catalog" `
    --paths "$projectRoot" `
    movie_catalog_app.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller завершился с ошибкой $LASTEXITCODE"
}

Write-Host "Готово: $projectRoot/dist/MovieCatalog.exe"
