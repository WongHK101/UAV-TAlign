[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$DatasetRoot = "",
    [string]$OutputRoot = "",
    [string]$EnvPrefix = "",
    [string]$PythonExe = "",
    [string]$Device = "cuda:0",
    [int[]]$Seeds = @(1, 2, 3),
    [string]$WindowTag = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Add-SummaryLine {
    param(
        [string]$Path,
        [string]$Line
    )
    Add-Content -Path $Path -Value $Line -Encoding UTF8
}

function Resolve-SubsetSceneNames {
    param(
        [string]$DatasetRootValue,
        [string[]]$TargetSceneIds
    )

    $sceneDirs = @(Get-ChildItem -Path $DatasetRootValue -Directory | Select-Object -ExpandProperty Name)
    $resolved = New-Object System.Collections.Generic.List[string]
    foreach ($sceneId in $TargetSceneIds) {
        $prefix = "$sceneId" + "_"
        $match = $sceneDirs | Where-Object { $_ -like ($prefix + "*") } | Select-Object -First 1
        if (-not $match) {
            throw "Could not resolve scene_id=$sceneId from dataset directories under $DatasetRootValue"
        }
        $resolved.Add([string]$match)
    }
    return ($resolved -join ",")
}

function Run-Stage {
    param(
        [string]$StageName,
        [string]$LogPath,
        [string]$FrameSelectionMode,
        [string]$ScenePassPolicy,
        [string]$AggregationMode,
        [int]$SeedValue,
        [string]$RunnerPath,
        [string]$PythonPath,
        [string]$DatasetRootValue,
        [string]$BundleRootValue,
        [string]$SceneNamesValue,
        [string]$DeviceValue,
        [string]$MinimaRootValue,
        [string]$SummaryPathValue
    )

    $stageOutputRoot = Join-Path $BundleRootValue ("prcv_ablation_" + $StageName)
    $null = New-Item -ItemType Directory -Force -Path $stageOutputRoot
    Add-Content -Path $LogPath -Value ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $StageName) -Encoding UTF8

    $args = @(
        $RunnerPath,
        "--dataset_root", $DatasetRootValue,
        "--output_root", $stageOutputRoot,
        "--methods", "uav_talign_full",
        "--scene_names", $SceneNamesValue,
        "--device", $DeviceValue,
        "--minima_root", $MinimaRootValue,
        "--uav_talign_minima_method", "roma",
        "--uav_talign_frame_count", "12",
        "--uav_talign_min_good_frames", "0",
        "--uav_talign_use_metadata_h0", "true",
        "--uav_talign_frame_selection_mode", $FrameSelectionMode,
        "--uav_talign_scene_pass_policy", $ScenePassPolicy,
        "--uav_talign_aggregation_mode", $AggregationMode,
        "--uav_talign_initial_candidate_ratio", "0.15",
        "--uav_talign_candidate_ratio_step", "0.15",
        "--uav_talign_max_candidate_ratio", "0.50",
        "--uav_talign_use_all_if_needed", "true",
        "--uav_talign_full_if_frames_le", "0",
        "--uav_talign_warning_min_accepted_ratio", "0.80",
        "--uav_talign_warning_max_severe_outlier_ratio", "0.10",
        "--uav_talign_warning_max_severe_outlier_count", "1",
        "--uav_talign_stability_warn_mean_px", "25.0",
        "--uav_talign_stability_max_reject_ratio", "0.25",
        "--uav_talign_max_severe_outliers", "0",
        "--seed", $SeedValue.ToString(),
        "--resume", "false",
        "--input_dynamic_range", "uint8",
        "--radiometric_mode", "raw_dn"
    )

    $stdoutPath = Join-Path $stageOutputRoot "_stage_stdout.txt"
    $stderrPath = Join-Path $stageOutputRoot "_stage_stderr.txt"
    $proc = Start-Process -FilePath $PythonPath -ArgumentList $args -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    if (Test-Path $stdoutPath) {
        Get-Content $stdoutPath | Add-Content -Path $LogPath -Encoding UTF8
    }
    if (Test-Path $stderrPath) {
        Get-Content $stderrPath | Add-Content -Path $LogPath -Encoding UTF8
    }
    $exitCode = [int]$proc.ExitCode
    Add-SummaryLine -Path $SummaryPathValue -Line "$StageName`:exit_code=$exitCode root=$stageOutputRoot"
    if ($exitCode -ne 0) {
        throw "Stage failed: $StageName exit_code=$exitCode"
    }
}

if (-not $WindowTag) {
    $WindowTag = Get-Date -Format "yyyyMMdd_HHmmss"
}
if (-not $RepoRoot) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}
$RepoRoot = Require-ExistingPath -PathValue $RepoRoot -Label "RepoRoot"

if (-not $DatasetRoot) {
    $DatasetRoot = Join-Path (Split-Path $RepoRoot -Parent) "UAV-TAlign-1K"
}
$DatasetRoot = Require-ExistingPath -PathValue $DatasetRoot -Label "DatasetRoot"

if (-not $EnvPrefix) {
    $EnvPrefix = Join-Path (Split-Path $RepoRoot -Parent) "uav_talign_envs\uav-talign-e10a8be-py310"
}
$EnvPrefix = Require-ExistingPath -PathValue $EnvPrefix -Label "EnvPrefix"

if (-not $PythonExe) {
    $PythonExe = Join-Path $EnvPrefix "python.exe"
}
$PythonExe = Require-ExistingPath -PathValue $PythonExe -Label "PythonExe"

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepoRoot "outputs"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$null = New-Item -ItemType Directory -Force -Path $OutputRoot

$RunnerPath = Require-ExistingPath -PathValue (Join-Path $RepoRoot "run_prcv_main_experiment.py") -Label "Main runner"
$MinimaRoot = Require-ExistingPath -PathValue (Join-Path $RepoRoot "third_party\MINIMA") -Label "MINIMA root"
$TargetSceneIds = @("01", "02", "03", "04", "07", "08", "13", "14")
$SceneNames = Resolve-SubsetSceneNames -DatasetRootValue $DatasetRoot -TargetSceneIds $TargetSceneIds

$BundleRoot = Join-Path $OutputRoot "ipt_p3p5_supplement_bundle_$WindowTag"
$AuditDir = Join-Path (Join-Path (Split-Path $RepoRoot -Parent) "_audit") "supplement_bundle_launch_$WindowTag"
$null = New-Item -ItemType Directory -Force -Path $BundleRoot
$null = New-Item -ItemType Directory -Force -Path $AuditDir

$SummaryPath = Join-Path $BundleRoot "launcher_summary.txt"
$AblationLogPath = Join-Path $BundleRoot "ablation_launcher.log"
$MultiSeedLogPath = Join-Path $BundleRoot "multiseed_launcher.log"
$LaunchNotePath = Join-Path $AuditDir "launch_note.txt"

Set-Content -Path $SummaryPath -Value @(
    "window_tag=$WindowTag",
    "repo_root=$RepoRoot",
    "dataset_root=$DatasetRoot",
    "python=$PythonExe",
    "device=$Device",
    "bundle_root=$BundleRoot",
    "scene_names=$SceneNames",
    "target_scene_ids=$($TargetSceneIds -join ',')",
    "seeds=$($Seeds -join ',')",
    "launched_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "launch_mode=inline_powershell"
) -Encoding UTF8
Set-Content -Path $AblationLogPath -Value @() -Encoding UTF8
Set-Content -Path $MultiSeedLogPath -Value @() -Encoding UTF8
Set-Content -Path $LaunchNotePath -Value @(
    "window_tag=$WindowTag",
    "repo_root=$RepoRoot",
    "dataset_root=$DatasetRoot",
    "bundle_root=$BundleRoot",
    "audit_dir=$AuditDir",
    "summary_path=$SummaryPath",
    "ablation_log=$AblationLogPath",
    "multiseed_log=$MultiSeedLogPath",
    "target_scene_ids=$($TargetSceneIds -join ',')",
    "launched_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "launch_mode=inline_powershell"
) -Encoding UTF8

Write-Output "RUN_ROOT=$BundleRoot"
Write-Output "AUDIT_DIR=$AuditDir"
Write-Output "MODE=inline_powershell"
Write-Output "STATUS=started"

try {
    Add-SummaryLine -Path $SummaryPath -Line "worker_started_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    Run-Stage `
        -StageName "A1_candidate_only" `
        -LogPath $AblationLogPath `
        -FrameSelectionMode "even" `
        -ScenePassPolicy "accepted_only" `
        -AggregationMode "single_best" `
        -SeedValue 0 `
        -RunnerPath $RunnerPath `
        -PythonPath $PythonExe `
        -DatasetRootValue $DatasetRoot `
        -BundleRootValue $BundleRoot `
        -SceneNamesValue $SceneNames `
        -DeviceValue $Device `
        -MinimaRootValue $MinimaRoot `
        -SummaryPathValue $SummaryPath

    Run-Stage `
        -StageName "A2_candidate_plus_aggregation" `
        -LogPath $AblationLogPath `
        -FrameSelectionMode "even" `
        -ScenePassPolicy "accepted_only" `
        -AggregationMode "robust_weighted" `
        -SeedValue 0 `
        -RunnerPath $RunnerPath `
        -PythonPath $PythonExe `
        -DatasetRootValue $DatasetRoot `
        -BundleRootValue $BundleRoot `
        -SceneNamesValue $SceneNames `
        -DeviceValue $Device `
        -MinimaRootValue $MinimaRoot `
        -SummaryPathValue $SummaryPath

    Run-Stage `
        -StageName "A3_candidate_plus_aggregation_plus_qa" `
        -LogPath $AblationLogPath `
        -FrameSelectionMode "even" `
        -ScenePassPolicy "qa_status" `
        -AggregationMode "robust_weighted" `
        -SeedValue 0 `
        -RunnerPath $RunnerPath `
        -PythonPath $PythonExe `
        -DatasetRootValue $DatasetRoot `
        -BundleRootValue $BundleRoot `
        -SceneNamesValue $SceneNames `
        -DeviceValue $Device `
        -MinimaRootValue $MinimaRoot `
        -SummaryPathValue $SummaryPath

    Run-Stage `
        -StageName "S1_random_selection_seed0" `
        -LogPath $AblationLogPath `
        -FrameSelectionMode "random" `
        -ScenePassPolicy "qa_status" `
        -AggregationMode "robust_weighted" `
        -SeedValue 0 `
        -RunnerPath $RunnerPath `
        -PythonPath $PythonExe `
        -DatasetRootValue $DatasetRoot `
        -BundleRootValue $BundleRoot `
        -SceneNamesValue $SceneNames `
        -DeviceValue $Device `
        -MinimaRootValue $MinimaRoot `
        -SummaryPathValue $SummaryPath

    foreach ($seed in $Seeds) {
        Run-Stage `
            -StageName ("S1_random_selection_seed" + $seed.ToString()) `
            -LogPath $MultiSeedLogPath `
            -FrameSelectionMode "random" `
            -ScenePassPolicy "qa_status" `
            -AggregationMode "robust_weighted" `
            -SeedValue ([int]$seed) `
            -RunnerPath $RunnerPath `
            -PythonPath $PythonExe `
            -DatasetRootValue $DatasetRoot `
            -BundleRootValue $BundleRoot `
            -SceneNamesValue $SceneNames `
            -DeviceValue $Device `
            -MinimaRootValue $MinimaRoot `
            -SummaryPathValue $SummaryPath
    }

    Add-SummaryLine -Path $SummaryPath -Line "exit_code=0"
    Add-SummaryLine -Path $SummaryPath -Line "worker_finished_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Output "STATUS=completed"
} catch {
    Add-SummaryLine -Path $SummaryPath -Line ("worker_error=" + $_.Exception.Message)
    Add-SummaryLine -Path $SummaryPath -Line "exit_code=1"
    Write-Output ("STATUS=failed:" + $_.Exception.Message)
    throw
}
