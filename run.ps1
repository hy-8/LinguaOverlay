param(
    [switch]$Diagnose,
    [switch]$ListDevices,
    [switch]$Mock,
    [double]$SmokeSeconds = 0
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectDir ".runtime"
$Arguments = @("$ProjectDir\app.py")

function Find-CondaExecutable {
    $Candidates = @(
        $env:CONDA_EXE,
        "D:\anaconda\Scripts\conda.exe",
        (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        (Join-Path $env:LOCALAPPDATA "miniconda3\Scripts\conda.exe"),
        (Join-Path $env:LOCALAPPDATA "anaconda3\Scripts\conda.exe")
    )

    $Command = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($Command) {
        $Candidates = @($Command.Source) + $Candidates
    }

    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate)) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    throw "Conda was not found. Install Miniconda/Anaconda or set CONDA_EXE."
}

if (-not (Test-Path (Join-Path $RuntimeDir "python.exe"))) {
    throw "Local runtime not found. Run .\install.ps1 -InstallCudaRuntime first."
}

$Conda = Find-CondaExecutable

if ($Diagnose) { $Arguments += "--diagnose" }
if ($ListDevices) { $Arguments += "--list-devices" }
if ($Mock) { $Arguments += "--mock" }
if ($SmokeSeconds -gt 0) {
    $Arguments += "--smoke-seconds"
    $Arguments += $SmokeSeconds.ToString([Globalization.CultureInfo]::InvariantCulture)
}

& $Conda run --no-capture-output --prefix $RuntimeDir python @Arguments
