param(
    [string]$PythonPath = "",
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$appDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverPath = Join-Path $appDirectory "server.py"
$localPython = Join-Path $appDirectory ".venv\Scripts\python.exe"
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = if (Test-Path -LiteralPath $localPython -PathType Leaf) { $localPython } else { "python" }
}
$version = & $PythonPath -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0) {
    throw "Python could not be started. Pass -PythonPath with a Python 3.11+ executable."
}
& $PythonPath -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 3)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is required." }
& $PythonPath -c "import numpy"
if ($LASTEXITCODE -ne 0) {
    throw "NumPy is required. Double-click setup_local.cmd once, then try again."
}
$arguments = @($serverPath, "--host", "127.0.0.1", "--port", $Port)
if (-not $NoBrowser) {
    $arguments += "--open"
}

Write-Host "Starting the posterior-pole eye parameter experiment application..."
Write-Host "Python: $version"
Write-Host "Local address: http://127.0.0.1:$Port/"
& $PythonPath @arguments
