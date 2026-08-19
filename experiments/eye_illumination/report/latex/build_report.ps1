param([string]$PythonPath = "")

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path (Join-Path $here "..\..\..\..")
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = (Get-Command python -ErrorAction Stop).Source
}
$xelatex = Get-Command xelatex -ErrorAction SilentlyContinue
if ($null -eq $xelatex) {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\MiKTeX\miktex\bin\x64\xelatex.exe"
    if (-not (Test-Path -LiteralPath $candidate)) { throw "XeLaTeX not found. Install MiKTeX or TeX Live." }
    $xelatexPath = $candidate
} else {
    $xelatexPath = $xelatex.Source
}

Push-Location $here
try {
    & $PythonPath generate_report_data.py
    if ($LASTEXITCODE -ne 0) { throw "Failed to generate LaTeX result tables." }
    & $PythonPath make_latex_figures.py
    if ($LASTEXITCODE -ne 0) { throw "Failed to generate report figures." }
    $reports = @("eye_illumination_experiment_report", "eye_illumination_experiment_report_en")
    foreach ($report in $reports) {
        foreach ($pass in 1..3) {
            & $xelatexPath --enable-installer -interaction=nonstopmode -halt-on-error -file-line-error "$report.tex"
            if ($LASTEXITCODE -ne 0) { throw "XeLaTeX failed for $report on pass $pass." }
        }
    }
    & $PythonPath validate_pdf.py
    if ($LASTEXITCODE -ne 0) { throw "PDF validation failed." }
    foreach ($report in $reports) {
        $log = Get-Content -Raw "$report.log"
        if ($log -match "undefined references|There were undefined citations") { throw "Unresolved references remain in $report.log." }
        if ($log -match "Overfull \\hbox") { throw "Overfull boxes remain in $report.log." }
    }
}
finally {
    Pop-Location
}
Write-Host "COMPLETE: Chinese and English LaTeX reports compiled and self-check passed."
