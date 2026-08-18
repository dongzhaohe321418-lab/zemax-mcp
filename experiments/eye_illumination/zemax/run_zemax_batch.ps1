param(
    [string]$OpticStudioDir = $env:ZEMAX_OPTICSTUDIO_DIR,
    [string]$PythonPath = "",
    [string]$OutputRoot = "",
    [string]$RunId = ""
)

$ErrorActionPreference = "Stop"
$batchDir = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$manifestPath = Join-Path $batchDir "manifest.json"
$casesPath = Join-Path $batchDir "cases.csv"
$sourcePath = Join-Path $PSScriptRoot "ZosApiEyeBatch.cs"
$verifierPath = Join-Path $PSScriptRoot "verify_zemax_results.py"
foreach ($requiredPath in @($manifestPath, $casesPath, $sourcePath, $verifierPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw "Missing batch file: $requiredPath" }
}
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($OpticStudioDir)) {
    $candidate = Get-ChildItem -LiteralPath "$env:ProgramFiles" -Directory -Filter "Ansys Zemax OpticStudio*" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($null -eq $candidate) { throw "Set -OpticStudioDir or ZEMAX_OPTICSTUDIO_DIR to the installed OpticStudio directory." }
    $OpticStudioDir = $candidate.FullName
}
$OpticStudioDir = (Resolve-Path -LiteralPath $OpticStudioDir).Path
foreach ($assembly in @("ZOSAPI.dll", "ZOSAPI_Interfaces.dll", "ZOSAPI_NetHelper.dll")) {
    if (-not (Test-Path -LiteralPath (Join-Path $OpticStudioDir $assembly) -PathType Leaf)) {
        throw "Missing $assembly under $OpticStudioDir. Compare this runner with the Standalone Application sample installed with your OpticStudio release."
    }
}
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = (Get-Command python -ErrorAction Stop).Source
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $batchDir "runs" }
if (-not (Test-Path -LiteralPath $OutputRoot)) { New-Item -ItemType Directory -Path $OutputRoot | Out-Null }
$OutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
if ([string]::IsNullOrWhiteSpace($RunId)) { $RunId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") }
if ($RunId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$') { throw "RunId contains unsupported characters." }
$runDir = Join-Path $OutputRoot ("{0}_{1}" -f $manifest.batch_id, $RunId)
if (Test-Path -LiteralPath $runDir) { throw "Refusing to overwrite an existing run directory: $runDir" }
$buildDir = Join-Path $runDir "_build"
New-Item -ItemType Directory -Path $runDir, $buildDir | Out-Null

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $csc -PathType Leaf)) { throw "64-bit .NET Framework C# compiler not found: $csc" }
foreach ($assembly in @("ZOSAPI.dll", "ZOSAPI_Interfaces.dll", "ZOSAPI_NetHelper.dll")) {
    Copy-Item -LiteralPath (Join-Path $OpticStudioDir $assembly) -Destination $buildDir
}
$runnerExe = Join-Path $buildDir "ZosApiEyeBatch.exe"
$zosApiDll = Join-Path $buildDir "ZOSAPI.dll"
$zosInterfacesDll = Join-Path $buildDir "ZOSAPI_Interfaces.dll"
$zosNetHelperDll = Join-Path $buildDir "ZOSAPI_NetHelper.dll"
$compileOutput = & $csc /nologo /platform:x64 /target:exe "/out:$runnerExe" `
    "/reference:$zosApiDll" `
    "/reference:$zosInterfacesDll" `
    "/reference:$zosNetHelperDll" `
    $sourcePath 2>&1
$compileExit = $LASTEXITCODE
$compileOutput | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $runDir "compile.log")
if ($compileExit -ne 0) { throw "ZOS-API runner compilation failed; inspect compile.log in $runDir" }

$env:ZEMAX_OPTICSTUDIO_DIR = $OpticStudioDir
$runnerOutput = & $runnerExe --cases $casesPath --output $runDir --batch-id $manifest.batch_id 2>&1
$runnerExit = $LASTEXITCODE
$runnerOutput | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $runDir "runner.log")

& $PythonPath $verifierPath --batch-dir $batchDir --results-dir $runDir
$verificationExit = $LASTEXITCODE
if ($runnerExit -ne 0) { throw "OpticStudio batch reported failures; inspect runner.log and verification_report.json in $runDir" }
if ($verificationExit -ne 0) { throw "Independent verification failed; inspect verification_report.json in $runDir" }

Write-Host "PASS: OpticStudio batch and independent verification completed."
Write-Host "BATCH_ID=$($manifest.batch_id)"
Write-Host "RUN_DIRECTORY=$runDir"
