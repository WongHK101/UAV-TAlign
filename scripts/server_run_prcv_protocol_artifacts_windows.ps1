[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$InputDir = "",
    [string]$OutputDir = "",
    [string]$CondaExe = "",
    [string]$EnvPrefix = "",
    [string]$WindowTag = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-CondaCommand {
    param([string]$RequestedPath)

    $candidates = New-Object System.Collections.Generic.List[string]
    if ($RequestedPath) {
        $candidates.Add($RequestedPath)
    }

    foreach ($name in @("conda.exe", "conda.bat", "conda")) {
        try {
            $cmd = Get-Command $name -ErrorAction Stop
            if ($cmd.Path) {
                $candidates.Add($cmd.Path)
            }
        } catch {
        }
    }

    foreach ($path in @(
        (Join-Path $env:USERPROFILE "anaconda3\condabin\conda.bat"),
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "miniconda3\condabin\conda.bat"),
        (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"),
        "C:\ProgramData\anaconda3\condabin\conda.bat",
        "C:\ProgramData\anaconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\condabin\conda.bat",
        "C:\ProgramData\miniconda3\Scripts\conda.exe"
    )) {
        if ($path) {
            $candidates.Add($path)
        }
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    throw "Could not resolve a usable conda command. Pass -CondaExe explicitly."
}

function Require-ExistingPath {
    param(
        [string]$PathValue,
        [string]$Label
    )
    if (-not (Test-Path $PathValue)) {
        throw "$Label not found: $PathValue"
    }
    return (Resolve-Path $PathValue).Path
}

function Write-SummaryLine {
    param(
        [string]$SummaryPath,
        [string]$Line
    )
    Add-Content -Path $SummaryPath -Value $Line -Encoding UTF8
}

if (-not $WindowTag) {
    $WindowTag = Get-Date -Format "yyyyMMdd_HHmmss"
}
if (-not $RepoRoot) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}
$RepoRoot = Require-ExistingPath -PathValue $RepoRoot -Label "RepoRoot"

if (-not $InputDir) {
    $InputDir = Join-Path $RepoRoot "outputs\ipt_p0c_12k_main"
}
$InputDir = Require-ExistingPath -PathValue $InputDir -Label "InputDir"

if (-not $OutputDir) {
    $OutputDir = Join-Path $RepoRoot "outputs\ipt_p0d_protocol_closure"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$null = New-Item -ItemType Directory -Force -Path $OutputDir

if (-not $EnvPrefix) {
    $EnvPrefix = Join-Path (Split-Path $RepoRoot -Parent) "uav_talign_envs\uav-talign-e10a8be-py310"
}
$EnvPrefix = Require-ExistingPath -PathValue $EnvPrefix -Label "EnvPrefix"

$CondaCommand = Resolve-CondaCommand -RequestedPath $CondaExe
$BuilderPath = Require-ExistingPath -PathValue (Join-Path $RepoRoot "scripts\build_ipt_p0d_protocol_artifacts.py") -Label "Protocol artifact builder"

$LauncherDir = Join-Path $OutputDir "_launcher"
$null = New-Item -ItemType Directory -Force -Path $LauncherDir
$SummaryPath = Join-Path $LauncherDir "summary.txt"
$BatchPath = Join-Path $LauncherDir "run_protocol_artifacts.cmd"
$StdoutPath = Join-Path $LauncherDir "builder_stdout.txt"
$StderrPath = Join-Path $LauncherDir "builder_stderr.txt"

Set-Content -Path $SummaryPath -Value @(
    "window_tag=$WindowTag",
    "repo_root=$RepoRoot",
    "input_dir=$InputDir",
    "output_dir=$OutputDir",
    "conda_command=$CondaCommand",
    "env_prefix=$EnvPrefix"
) -Encoding UTF8

$builderArgs = @(
    "--input_dir `"$InputDir`"",
    "--output_dir `"$OutputDir`""
)

$batchLines = New-Object System.Collections.Generic.List[string]
$batchLines.Add("@echo off")
$batchLines.Add("setlocal")
$batchLines.Add("call `"$CondaCommand`" run -p `"$EnvPrefix`" python `"$BuilderPath`" ^")
for ($i = 0; $i -lt $builderArgs.Count; $i++) {
    $suffix = if ($i -eq $builderArgs.Count - 1) { " 1>`"$StdoutPath`" 2>`"$StderrPath`"" } else { " ^" }
    $batchLines.Add("  $($builderArgs[$i])$suffix")
}
$batchLines.Add("if errorlevel 1 exit /b %errorlevel%")
$batchLines.Add("exit /b 0")
Set-Content -Path $BatchPath -Value $batchLines -Encoding ASCII

Write-SummaryLine -SummaryPath $SummaryPath -Line "launcher_batch=$BatchPath"
Write-SummaryLine -SummaryPath $SummaryPath -Line "builder_stdout=$StdoutPath"
Write-SummaryLine -SummaryPath $SummaryPath -Line "builder_stderr=$StderrPath"

$process = Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/c", "`"$BatchPath`"") -Wait -PassThru -NoNewWindow
$exitCode = [int]$process.ExitCode
Write-SummaryLine -SummaryPath $SummaryPath -Line "builder_exit_code=$exitCode"
if ($exitCode -ne 0) {
    throw "Protocol artifact builder failed with exit code $exitCode. See $SummaryPath."
}

$requiredFiles = @(
    "per_scene_reliability_table.csv",
    "threshold_sensitivity.csv",
    "condition_reliability_profile.csv",
    "risk_coverage.csv",
    "canonical_operating_point.csv",
    "paper_facing_summary.md"
)

$missing = @()
foreach ($name in $requiredFiles) {
    $path = Join-Path $OutputDir $name
    $exists = Test-Path $path
    Write-SummaryLine -SummaryPath $SummaryPath -Line "$name=$exists"
    if (-not $exists) {
        $missing += $path
    }
}

if ($missing.Count -gt 0) {
    throw "Protocol artifacts are incomplete. Missing: $($missing -join ', ')"
}

Write-Output $SummaryPath
