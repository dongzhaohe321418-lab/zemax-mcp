param(
    [string]$PythonPath = "",
    [string]$OpticStudioDir = $env:ZEMAX_OPTICSTUDIO_DIR,
    [string]$NodePath = "",
    [string]$ReportBuilderPath = ""
)

$ErrorActionPreference = "Stop"
$experimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Resolve-Path (Join-Path $experimentDir "..\..")
$buildDir = Join-Path $repoDir ".build\eye_illumination"
$resultDir = Join-Path $experimentDir "results\zemax"

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = (Get-Command python -ErrorAction Stop).Source
}
if ([string]::IsNullOrWhiteSpace($OpticStudioDir)) {
    $candidate = Get-ChildItem -LiteralPath "$env:ProgramFiles" -Directory -Filter "Ansys Zemax OpticStudio*" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($null -eq $candidate) { throw "Set ZEMAX_OPTICSTUDIO_DIR to the OpticStudio installation directory." }
    $OpticStudioDir = $candidate.FullName
}
foreach ($required in @("ZOSAPI.dll", "ZOSAPI_Interfaces.dll", "ZOSAPI_NetHelper.dll")) {
    if (-not (Test-Path -LiteralPath (Join-Path $OpticStudioDir $required))) {
        throw "Missing $required under $OpticStudioDir"
    }
}

New-Item -ItemType Directory -Force -Path $buildDir, $resultDir | Out-Null
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $csc)) { throw "64-bit C# compiler not found: $csc" }
Copy-Item -LiteralPath (Join-Path $OpticStudioDir "ZOSAPI.dll") -Destination $buildDir -Force
Copy-Item -LiteralPath (Join-Path $OpticStudioDir "ZOSAPI_Interfaces.dll") -Destination $buildDir -Force
Copy-Item -LiteralPath (Join-Path $OpticStudioDir "ZOSAPI_NetHelper.dll") -Destination $buildDir -Force

Push-Location $repoDir
try {
    & $PythonPath "experiments\eye_illumination\run_experiment.py"
    if ($LASTEXITCODE -ne 0) { throw "Independent model failed." }

    & $csc /nologo /platform:x64 /target:exe /out:"$buildDir\ZosApiEyeValidation.exe" /reference:"$buildDir\ZOSAPI.dll" /reference:"$buildDir\ZOSAPI_Interfaces.dll" /reference:"$buildDir\ZOSAPI_NetHelper.dll" "experiments\eye_illumination\zemax\ZosApiEyeValidation.cs"
    if ($LASTEXITCODE -ne 0) { throw "ZOS-API validator compilation failed." }
    $env:ZEMAX_OPTICSTUDIO_DIR = $OpticStudioDir
    $env:EYE_EXPERIMENT_ZEMAX_DIR = $resultDir
    & "$buildDir\ZosApiEyeValidation.exe"
    if ($LASTEXITCODE -ne 0) { throw "ZOS-API validation run failed." }

    & $PythonPath "experiments\eye_illumination\validate_results.py"
    if ($LASTEXITCODE -ne 0) { throw "Result validation failed." }
    & $PythonPath "experiments\eye_illumination\validate_real_experiment_readiness.py"
    if ($LASTEXITCODE -ne 0) { throw "Real-experiment readiness audit failed to reproduce the model." }
    & $PythonPath "experiments\eye_illumination\make_notebook.py"
    if ($LASTEXITCODE -ne 0) { throw "Notebook generation failed." }
    & $PythonPath -m jupyter execute "experiments\eye_illumination\notebooks\eye_illumination_analysis.ipynb" --inplace
    if ($LASTEXITCODE -ne 0) { throw "Notebook execution failed." }
    & $PythonPath -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
    & $PythonPath "experiments\eye_illumination\make_report_artifact.py"
    if ($LASTEXITCODE -ne 0) { throw "Report artifact generation failed." }

    if ([string]::IsNullOrWhiteSpace($NodePath)) {
        $NodePath = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\OpenAI\Codex\runtimes" -Filter node.exe -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if ([string]::IsNullOrWhiteSpace($ReportBuilderPath)) {
        $ReportBuilderPath = Get-ChildItem -LiteralPath "$env:USERPROFILE\.codex\plugins\cache\openai-curated-remote\data-analytics" -Filter deliver_portable_artifact.mjs -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not [string]::IsNullOrWhiteSpace($NodePath) -and -not [string]::IsNullOrWhiteSpace($ReportBuilderPath)) {
        & $NodePath $ReportBuilderPath --input "experiments\eye_illumination\report\artifact.json" --output "experiments\eye_illumination\report\eye_illumination_report.html"
        if ($LASTEXITCODE -ne 0) { throw "Portable report rendering failed." }
    } else {
        Write-Warning "Canonical artifact created; portable HTML skipped because Node or report builder was not found."
    }
}
finally {
    Pop-Location
}

Write-Host "COMPLETE: independent model, OpticStudio validation, notebook, tests, and report artifact."
