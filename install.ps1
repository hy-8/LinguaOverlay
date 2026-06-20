param(
    [switch]$InstallCudaRuntime
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectDir ".runtime"

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

$Conda = Find-CondaExecutable

if (-not (Test-Path (Join-Path $RuntimeDir "python.exe"))) {
    & $Conda create --prefix $RuntimeDir -c conda-forge python=3.11 pip -y
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the Conda environment" }
}

if ($InstallCudaRuntime) {
    & $Conda install --prefix $RuntimeDir -c "nvidia/label/cuda-12.8.1" cuda-runtime=12.8 -y
    if ($LASTEXITCODE -ne 0) { throw "Failed to install the CUDA 12.8 runtime" }
    & $Conda install --prefix $RuntimeDir -c conda-forge cudnn=9 -y
    if ($LASTEXITCODE -ne 0) { throw "Failed to install cuDNN 9" }
}

& $Conda run --prefix $RuntimeDir python -m pip install --upgrade pip
& $Conda run --prefix $RuntimeDir python -m pip install -r "$ProjectDir\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "Failed to install Python dependencies" }

Write-Host ""
Write-Host "Installation completed. Run:"
Write-Host "  .\run.ps1 -Diagnose"
Write-Host "  .\run.ps1 -Mock"
