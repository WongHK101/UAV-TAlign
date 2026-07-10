[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$DatasetRoot = "",
    [string]$ManifestPath = "",
    [string]$OutputRoot = "",
    [string]$CondaExe = "",
    [string]$EnvPrefix = "",
    [string]$Methods = "sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full",
    [string]$Device = "cuda:0",
    [string]$OfficialXoftrCkpt = "",
    [string]$RawMinimaMethod = "roma",
    [string]$RawMinimaCkpt = "",
    [string]$UavTalignMinimaMethod = "roma",
    [string]$UavTalignMinimaCkpt = "",
    [int]$LoftrMatchMaxDim = 1200,
    [bool]$LoftrUseAmp = $true,
    [int]$Seed = 0,
    [bool]$Resume = $false,
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

if (-not $DatasetRoot) {
    $DatasetRoot = Join-Path (Split-Path $RepoRoot -Parent) "UAV-TAlign-12K"
}
$DatasetRoot = Require-ExistingPath -PathValue $DatasetRoot -Label "DatasetRoot"

if (-not $ManifestPath) {
    $ManifestPath = Join-Path $RepoRoot "manifests\UAV-TAlign-12K_official_valid_evaluation_manifest.json"
}
$ManifestPath = Require-ExistingPath -PathValue $ManifestPath -Label "ManifestPath"

if (-not $EnvPrefix) {
    $EnvPrefix = Join-Path (Split-Path $RepoRoot -Parent) "uav_talign_envs\uav-talign-e10a8be-py310"
}
$EnvPrefix = Require-ExistingPath -PathValue $EnvPrefix -Label "EnvPrefix"

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepoRoot "outputs\ipt_p0c_12k_main"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$null = New-Item -ItemType Directory -Force -Path $OutputRoot

$CondaCommand = Resolve-CondaCommand -RequestedPath $CondaExe
$RunnerPath = Require-ExistingPath -PathValue (Join-Path $RepoRoot "run_prcv_main_experiment.py") -Label "Main runner"
$ValidatorPath = Require-ExistingPath -PathValue (Join-Path $RepoRoot "scripts\check_prcv_main_outputs.py") -Label "Output validator"
$MinimaRoot = Require-ExistingPath -PathValue (Join-Path $RepoRoot "third_party\MINIMA") -Label "MINIMA root"

$MethodList = @($Methods.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($MethodList -contains "xoftr_official") {
    if (-not $OfficialXoftrCkpt) {
        throw "OfficialXoftrCkpt is required when xoftr_official is in -Methods."
    }
    $OfficialXoftrCkpt = Require-ExistingPath -PathValue $OfficialXoftrCkpt -Label "OfficialXoftrCkpt"
}
if ($RawMinimaCkpt) {
    $RawMinimaCkpt = Require-ExistingPath -PathValue $RawMinimaCkpt -Label "RawMinimaCkpt"
}
if ($UavTalignMinimaCkpt) {
    $UavTalignMinimaCkpt = Require-ExistingPath -PathValue $UavTalignMinimaCkpt -Label "UavTalignMinimaCkpt"
}

$LauncherDir = Join-Path $OutputRoot "_launcher"
$null = New-Item -ItemType Directory -Force -Path $LauncherDir
$SummaryPath = Join-Path $LauncherDir "summary.txt"
$BatchPath = Join-Path $LauncherDir "run_main_12k.cmd"
$MainStdoutPath = Join-Path $LauncherDir "main_stdout.txt"
$MainStderrPath = Join-Path $LauncherDir "main_stderr.txt"
$ValidateStdoutPath = Join-Path $LauncherDir "validate_stdout.txt"
$ValidateStderrPath = Join-Path $LauncherDir "validate_stderr.txt"

Set-Content -Path $SummaryPath -Value @(
    "window_tag=$WindowTag",
    "repo_root=$RepoRoot",
    "dataset_root=$DatasetRoot",
    "manifest_path=$ManifestPath",
    "output_root=$OutputRoot",
    "conda_command=$CondaCommand",
    "env_prefix=$EnvPrefix",
    "methods=$Methods",
    "device=$Device",
    "loftr_match_max_dim=$LoftrMatchMaxDim",
    "loftr_use_amp=$($LoftrUseAmp.ToString().ToLowerInvariant())",
    "seed=$Seed",
    "resume=$($Resume.ToString().ToLowerInvariant())"
) -Encoding UTF8

$mainArgs = @(
    "--dataset_root `"$DatasetRoot`"",
    "--manifest_path `"$ManifestPath`"",
    "--output_root `"$OutputRoot`"",
    "--methods `"$Methods`"",
    "--device `"$Device`"",
    "--loftr_match_max_dim $LoftrMatchMaxDim",
    "--loftr_use_amp $($LoftrUseAmp.ToString().ToLowerInvariant())",
    "--minima_root `"$MinimaRoot`"",
    "--raw_minima_method `"$RawMinimaMethod`"",
    "--uav_talign_minima_method `"$UavTalignMinimaMethod`"",
    "--seed $Seed",
    "--resume $($Resume.ToString().ToLowerInvariant())"
)
if ($OfficialXoftrCkpt) {
    $mainArgs += "--official_xoftr_ckpt `"$OfficialXoftrCkpt`""
}
if ($RawMinimaCkpt) {
    $mainArgs += "--raw_minima_ckpt `"$RawMinimaCkpt`""
}
if ($UavTalignMinimaCkpt) {
    $mainArgs += "--uav_talign_minima_ckpt `"$UavTalignMinimaCkpt`""
}

$validateArgs = @(
    "--output_dir `"$OutputRoot`"",
    "--required_methods `"$Methods`""
)

$batchLines = New-Object System.Collections.Generic.List[string]
$batchLines.Add("@echo off")
$batchLines.Add("setlocal")
$batchLines.Add("call `"$CondaCommand`" run -p `"$EnvPrefix`" python `"$RunnerPath`" ^")
for ($i = 0; $i -lt $mainArgs.Count; $i++) {
    $suffix = if ($i -eq $mainArgs.Count - 1) { " 1>`"$MainStdoutPath`" 2>`"$MainStderrPath`"" } else { " ^" }
    $batchLines.Add("  $($mainArgs[$i])$suffix")
}
$batchLines.Add("if errorlevel 1 exit /b %errorlevel%")
$batchLines.Add("call `"$CondaCommand`" run -p `"$EnvPrefix`" python `"$ValidatorPath`" ^")
for ($i = 0; $i -lt $validateArgs.Count; $i++) {
    $suffix = if ($i -eq $validateArgs.Count - 1) { " 1>`"$ValidateStdoutPath`" 2>`"$ValidateStderrPath`"" } else { " ^" }
    $batchLines.Add("  $($validateArgs[$i])$suffix")
}
$batchLines.Add("if errorlevel 1 exit /b %errorlevel%")
$batchLines.Add("exit /b 0")
Set-Content -Path $BatchPath -Value $batchLines -Encoding ASCII

Write-SummaryLine -SummaryPath $SummaryPath -Line "launcher_batch=$BatchPath"
Write-SummaryLine -SummaryPath $SummaryPath -Line "main_stdout=$MainStdoutPath"
Write-SummaryLine -SummaryPath $SummaryPath -Line "main_stderr=$MainStderrPath"
Write-SummaryLine -SummaryPath $SummaryPath -Line "validate_stdout=$ValidateStdoutPath"
Write-SummaryLine -SummaryPath $SummaryPath -Line "validate_stderr=$ValidateStderrPath"

$process = Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/c", "`"$BatchPath`"") -Wait -PassThru -NoNewWindow
$exitCode = [int]$process.ExitCode
Write-SummaryLine -SummaryPath $SummaryPath -Line "exit_code=$exitCode"

if ($exitCode -ne 0) {
    throw "Main 12K launcher failed with exit code $exitCode. See $SummaryPath."
}

Write-Output $SummaryPath
