$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoUrl = "https://github.com/lik710919-cpu/maibao-zero-cost-compute-v0.git"
$BootstrapRoot = Join-Path $env:LOCALAPPDATA "Maibao\authorization-bootstrap"
$RepoDir = Join-Path $BootstrapRoot "repo"
$UnifiedAuth = "experiments/zero_cost_compute_v0/unified_auth.py"

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $Name"
    }
}

if (-not (Get-Command glab -ErrorAction SilentlyContinue)) {
    Assert-Command "winget"
    winget install --id GLab.GLab --exact --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install the official GitLab CLI."
    }

    $UserBinCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"),
        (Join-Path $env:LOCALAPPDATA "Programs\GitLab CLI")
    )
    foreach ($Candidate in $UserBinCandidates) {
        if ((Test-Path $Candidate) -and ($env:PATH -notlike "*$Candidate*")) {
            $env:PATH = "$Candidate;$env:PATH"
        }
    }
}

Assert-Command "git"
Assert-Command "python"
Assert-Command "glab"

New-Item -ItemType Directory -Force -Path $BootstrapRoot | Out-Null

if (-not (Test-Path (Join-Path $RepoDir ".git"))) {
    if (Test-Path $RepoDir) {
        Remove-Item -Recurse -Force $RepoDir
    }
    git clone --no-checkout $RepoUrl $RepoDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the isolated authorization bootstrap checkout."
    }
}

Push-Location $RepoDir
try {
    $RemoteUrl = (git remote get-url origin).Trim()
    if ($RemoteUrl -ne $RepoUrl) {
        throw "Bootstrap repository origin does not match the approved remote."
    }

    git fetch --prune origin main
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to fetch the remote main baseline."
    }

    git checkout --detach --force origin/main
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to detach the bootstrap checkout at origin/main."
    }

    git clean -ffd
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to clean the isolated bootstrap checkout."
    }

    if (-not (Test-Path $UnifiedAuth)) {
        throw "Unified authorization entry point is missing from remote main."
    }

    python $UnifiedAuth onboard --provider gitlab
    if ($LASTEXITCODE -ne 0) {
        throw "Unified GitLab onboarding did not complete."
    }
}
finally {
    Pop-Location
}
