#!/usr/bin/env bash
set -u
set -o pipefail

REPO_ROOT="${REPO_ROOT:-/home/user2/whk/UAV-TAlign}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$REPO_ROOT/outputs}"
CONDA_BIN="${CONDA_BIN:-/home/user2/anaconda3/bin/conda}"
ENV_NAME="${ENV_NAME:-uav-talign}"
GPU0_IDLE_MEM_MAX_MB="${GPU0_IDLE_MEM_MAX_MB:-1024}"
GPU0_IDLE_UTIL_MAX="${GPU0_IDLE_UTIL_MAX:-15}"
GPU0_WAIT_TIMEOUT_MIN="${GPU0_WAIT_TIMEOUT_MIN:-120}"
GPU0_WAIT_INTERVAL_SEC="${GPU0_WAIT_INTERVAL_SEC:-60}"
WINDOW_TAG="${WINDOW_TAG:-$(date +%Y%m%d_%H%M%S)}"
LOG_ROOT="${LOG_ROOT:-$OUTPUT_ROOT/prcv_ablation_wave_${WINDOW_TAG}}"
LOG_DIR="$LOG_ROOT/_launcher"
LOG_FILE="$LOG_DIR/launcher.log"
SUMMARY_FILE="$LOG_DIR/summary.txt"

SCENE_NAMES="01_day_grayscale_wide_substation_power_lines_50,02_day_grayscale_zoom_substation_power_lines_50,03_night_grayscale_wide_substation_power_lines_45,04_night_grayscale_zoom_substation_power_lines_45,07_day_grayscale_transmission_tower_102,08_night_grayscale_urban_22,13_lowlight_pseudocolor_road_21,14_lowlight_pseudocolor_transmission_tower_18"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

declare -A STAGE_ROOTS
declare -A STAGE_EXIT_CODES

log() {
  printf '[%s] %s\n' "$(date '+%F %T %z')" "$*"
}

append_summary() {
  printf '%s\n' "$*" >> "$SUMMARY_FILE"
}

gpu_snapshot() {
  nvidia-smi --query-gpu=index,name,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits
}

gpu0_idle() {
  GPU0_IDLE_MEM_MAX_MB="$GPU0_IDLE_MEM_MAX_MB" \
  GPU0_IDLE_UTIL_MAX="$GPU0_IDLE_UTIL_MAX" \
  "$PYTHON_BIN" - <<'PY'
import os
import subprocess
import sys

gpu_lines = subprocess.check_output(
    [
        "nvidia-smi",
        "--query-gpu=index,uuid,memory.used,utilization.gpu",
        "--format=csv,noheader,nounits",
    ],
    text=True,
).strip().splitlines()
apps_text = subprocess.check_output(
    [
        "nvidia-smi",
        "--query-compute-apps=gpu_uuid,pid,used_gpu_memory",
        "--format=csv,noheader,nounits",
    ],
    text=True,
    stderr=subprocess.DEVNULL,
).strip()

mem_limit = int(os.environ.get("GPU0_IDLE_MEM_MAX_MB", "1024"))
util_limit = int(os.environ.get("GPU0_IDLE_UTIL_MAX", "15"))

gpu0 = None
for line in gpu_lines:
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 4:
        continue
    if parts[0] == "0":
        gpu0 = {"uuid": parts[1], "mem_used": int(parts[2]), "util": int(parts[3])}
        break

if gpu0 is None:
    sys.exit(2)

app_count = 0
if apps_text:
    for line in apps_text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[0] == gpu0["uuid"]:
            app_count += 1

busy = app_count > 0 or gpu0["mem_used"] > mem_limit or gpu0["util"] > util_limit
sys.exit(1 if busy else 0)
PY
}

wait_for_gpu0_idle() {
  local waited_sec=0
  local timeout_sec=$((GPU0_WAIT_TIMEOUT_MIN * 60))
  while (( waited_sec <= timeout_sec )); do
    log "GPU snapshot:"
    gpu_snapshot
    if gpu0_idle; then
      log "GPU0 is idle and safe to use."
      return 0
    fi
    if (( waited_sec == timeout_sec )); then
      break
    fi
    log "GPU0 still busy; waiting ${GPU0_WAIT_INTERVAL_SEC}s before retry."
    sleep "$GPU0_WAIT_INTERVAL_SEC"
    waited_sec=$((waited_sec + GPU0_WAIT_INTERVAL_SEC))
  done
  log "GPU0 did not become idle within ${GPU0_WAIT_TIMEOUT_MIN} minutes."
  return 1
}

summarize_stage() {
  local stage_name="$1"
  local stage_root="$2"
  local summary_json="$stage_root/main_experiment_summary.json"
  if [[ ! -f "$summary_json" ]]; then
    log "${stage_name}: summary JSON missing at $summary_json"
    append_summary "${stage_name}: summary_missing root=$stage_root"
    return 1
  fi
  "$PYTHON_BIN" - "$stage_name" "$summary_json" >> "$SUMMARY_FILE" <<'PY'
import json
import pathlib
import sys

stage_name = sys.argv[1]
summary_path = pathlib.Path(sys.argv[2])
payload = json.loads(summary_path.read_text(encoding="utf-8"))
method = payload.get("method_summaries", {}).get("uav_talign_full", {})
status_counts = method.get("status_counts", {})
qa_counts = method.get("qa_status_counts", {})
accepted = method.get("accepted_frames_summary", {})
runtime = method.get("runtime_sec_summary", {})
print(
    f"{stage_name}: root={summary_path.parent} "
    f"status_counts={status_counts} qa_status_counts={qa_counts} "
    f"accepted_mean={accepted.get('mean')} runtime_mean={runtime.get('mean')}"
)
PY
}

run_stage() {
  local stage_name="$1"
  local frame_selection_mode="$2"
  local aggregation_mode="$3"
  local scene_pass_policy="$4"

  local stage_root="$OUTPUT_ROOT/prcv_ablation_${stage_name}_${WINDOW_TAG}"
  STAGE_ROOTS["$stage_name"]="$stage_root"

  log "${stage_name}: starting."
  log "${stage_name}: output_root=$stage_root"

  CUDA_VISIBLE_DEVICES=0 \
  "$CONDA_BIN" run -n "$ENV_NAME" \
    python "$REPO_ROOT/run_prcv_main_experiment.py" \
    --dataset_root "$REPO_ROOT/UAV-TAlign-1K" \
    --output_root "$stage_root" \
    --methods "uav_talign_full" \
    --scene_names "$SCENE_NAMES" \
    --device "cuda:0" \
    --minima_root "$REPO_ROOT/third_party/MINIMA" \
    --uav_talign_minima_method "roma" \
    --uav_talign_frame_count 12 \
    --uav_talign_min_good_frames 0 \
    --uav_talign_use_metadata_h0 true \
    --uav_talign_frame_selection_mode "$frame_selection_mode" \
    --uav_talign_scene_pass_policy "$scene_pass_policy" \
    --uav_talign_aggregation_mode "$aggregation_mode" \
    --uav_talign_initial_candidate_ratio 0.15 \
    --uav_talign_candidate_ratio_step 0.15 \
    --uav_talign_max_candidate_ratio 0.50 \
    --uav_talign_use_all_if_needed true \
    --uav_talign_full_if_frames_le 0 \
    --uav_talign_warning_min_accepted_ratio 0.80 \
    --uav_talign_warning_max_severe_outlier_ratio 0.10 \
    --uav_talign_warning_max_severe_outlier_count 1 \
    --uav_talign_stability_warn_mean_px 25.0 \
    --uav_talign_stability_max_reject_ratio 0.25 \
    --uav_talign_max_severe_outliers 0 \
    --seed 0 \
    --resume false \
    --input_dynamic_range uint8 \
    --radiometric_mode raw_dn
  local rc=$?

  STAGE_EXIT_CODES["$stage_name"]=$rc
  log "${stage_name}: exit_code=$rc"
  append_summary "${stage_name}: exit_code=$rc root=$stage_root"
  summarize_stage "$stage_name" "$stage_root" || true
  return $rc
}

main() {
  log "Starting PRCV ablation wave launcher."
  log "REPO_ROOT=$REPO_ROOT"
  log "OUTPUT_ROOT=$OUTPUT_ROOT"
  log "WINDOW_TAG=$WINDOW_TAG"
  mkdir -p "$OUTPUT_ROOT"
  : > "$SUMMARY_FILE"
  append_summary "window_tag=$WINDOW_TAG"
  append_summary "repo_root=$REPO_ROOT"
  append_summary "output_root=$OUTPUT_ROOT"
  append_summary "scene_names=$SCENE_NAMES"

  if [[ ! -x "$CONDA_BIN" ]]; then
    log "Conda binary not found: $CONDA_BIN"
    append_summary "fatal: missing_conda_bin=$CONDA_BIN"
    return 2
  fi
  if [[ ! -f "$REPO_ROOT/run_prcv_main_experiment.py" ]]; then
    log "Runner missing: $REPO_ROOT/run_prcv_main_experiment.py"
    append_summary "fatal: missing_runner=$REPO_ROOT/run_prcv_main_experiment.py"
    return 2
  fi

  if ! wait_for_gpu0_idle; then
    append_summary "window_result=missed_gpu0_busy"
    return 20
  fi

  run_stage "A1_candidate_only" "even" "single_best" "accepted_only"

  run_stage "A2_candidate_plus_aggregation" "even" "robust_weighted" "accepted_only"

  run_stage "A3_candidate_plus_aggregation_plus_qa" "even" "robust_weighted" "qa_status"

  if [[ "${STAGE_EXIT_CODES[A3_candidate_plus_aggregation_plus_qa]:-1}" -eq 0 ]]; then
    run_stage "S1_random_selection" "random" "robust_weighted" "qa_status"
  else
    log "S1_random_selection skipped because A3 did not complete cleanly."
    append_summary "S1_random_selection: skipped"
  fi

  log "Final stage roots:"
  for key in "${!STAGE_ROOTS[@]}"; do
    log "  $key -> ${STAGE_ROOTS[$key]} (rc=${STAGE_EXIT_CODES[$key]:-NA})"
    append_summary "$key: final_root=${STAGE_ROOTS[$key]} final_rc=${STAGE_EXIT_CODES[$key]:-NA}"
  done
  append_summary "window_result=completed"
  log "PRCV ablation wave launcher finished."
  return 0
}

main "$@"
