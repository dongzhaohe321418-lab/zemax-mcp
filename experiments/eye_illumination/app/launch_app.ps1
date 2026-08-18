param(
    [string]$PythonPath = "python",
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$appDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverPath = Join-Path $appDirectory "server.py"
$version = & $PythonPath -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0) {
    throw "Python could not be started. Pass -PythonPath with a Python 3.11+ executable."
}
& $PythonPath -c "import numpy"
if ($LASTEXITCODE -ne 0) {
    throw "NumPy is required. From the repository root run: python -m pip install -e `".[dev,analysis]`""
}
$arguments = @($serverPath, "--host", "127.0.0.1", "--port", $Port)
if (-not $NoBrowser) {
    $arguments += "--open"
}

Write-Host "Starting the fixed-focal eye experiment application..."
Write-Host "Python: $version"
Write-Host "Local address: http://127.0.0.1:$Port/"
& $PythonPath @arguments
