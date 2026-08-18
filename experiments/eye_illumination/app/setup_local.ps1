param(
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$appDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDirectory = Join-Path $appDirectory ".venv"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"
$requirementsPath = Join-Path $appDirectory "requirements.txt"

if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    Write-Host "Local environment already exists; refreshing dependencies..."
} else {
    if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
        $basePython = $PythonPath
        $baseArguments = @()
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $basePython = (Get-Command py).Source
        $baseArguments = @("-3")
    } else {
        $basePython = (Get-Command python -ErrorAction Stop).Source
        $baseArguments = @()
    }
    & $basePython @baseArguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 3)"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is required." }
    Write-Host "Creating the private local Python environment..."
    & $basePython @baseArguments -m venv $venvDirectory
    if ($LASTEXITCODE -ne 0) { throw "Could not create the local Python environment." }
}

Write-Host "Installing the small, pinned runtime dependency set..."
& $venvPython -m pip install --disable-pip-version-check -r $requirementsPath
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $venvPython -c "import numpy, sys; print(f'Ready: Python {sys.version.split()[0]}, NumPy {numpy.__version__}')"
if ($LASTEXITCODE -ne 0) { throw "Local environment self-check failed." }

Write-Host ""
Write-Host "Setup complete. Double-click launch_app.cmd to start the Web GUI."
