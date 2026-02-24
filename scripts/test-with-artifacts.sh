#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR="${ARTIFACT_DIR:-artifacts/test}"
MODE="${1:-all}"
STRICT_ARTIFACTS="${STRICT_ARTIFACTS:-0}"
overall_rc=0
mkdir -p "$ARTIFACT_DIR"

pkg_json="package.json"
has_pkg=false
if [[ -f "$pkg_json" ]]; then
  has_pkg=true
fi

has_pkg_script() {
  local key="$1"
  [[ "$has_pkg" == true ]] || return 1
  jq -e --arg key "$key" '.scripts[$key] != null' "$pkg_json" >/dev/null 2>&1
}

pkg_script_cmd() {
  local key="$1"
  jq -r --arg key "$key" '.scripts[$key] // ""' "$pkg_json"
}

detect_runner() {
  if [[ "$has_pkg" != true ]]; then
    echo ""
    return
  fi
  local pm
  pm="$(jq -r '.packageManager // ""' "$pkg_json" 2>/dev/null || true)"
  if [[ "$pm" == pnpm* || -f pnpm-lock.yaml ]]; then
    echo "pnpm"
  elif [[ "$pm" == bun* || -f bun.lockb ]]; then
    echo "bun"
  else
    echo "npm"
  fi
}

RUNNER="$(detect_runner)"

run_logged() {
  local name="$1"
  local cmd="$2"
  local log_file="$ARTIFACT_DIR/test-output-${name}.log"
  local summary_file="$ARTIFACT_DIR/summary-${name}.json"
  local started ended status duration_ms

  started="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  local start_epoch
  start_epoch="$(date +%s)"

  set +e
  bash -lc "$cmd" 2>&1 | tee "$log_file"
  status=${PIPESTATUS[0]}
  set -e

  ended="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  local end_epoch
  end_epoch="$(date +%s)"
  duration_ms=$(( (end_epoch - start_epoch) * 1000 ))

  jq -n \
    --arg name "$name" \
    --arg command "$cmd" \
    --arg started_at "$started" \
    --arg ended_at "$ended" \
    --argjson exit_code "$status" \
    --argjson duration_ms "$duration_ms" \
    '{name:$name,command:$command,started_at:$started_at,ended_at:$ended_at,exit_code:$exit_code,duration_ms:$duration_ms}' > "$summary_file"

  return "$status"
}

run_step() {
  local name="$1"
  local cmd="$2"
  if ! run_logged "$name" "$cmd"; then
    overall_rc=1
    return 1
  fi
  return 0
}

run_pkg_script() {
  local script_name="$1"
  local name="$2"

  if ! has_pkg_script "$script_name"; then
    echo "[test-with-artifacts] package script '$script_name' not present, skipping"
    return 0
  fi

  case "$RUNNER" in
    pnpm)
      run_step "$name" "pnpm run $script_name"
      ;;
    bun)
      if ! command -v bun >/dev/null 2>&1; then
        echo "[test-with-artifacts] bun not found; skipping bun-based script '$script_name'"
        jq -n --arg name "$name" --arg script "$script_name" --arg reason "bun_not_found" '{name:$name,script:$script,status:"skipped",reason:$reason}' > "$ARTIFACT_DIR/summary-${name}.json"
        return 0
      fi
      run_step "$name" "bun run $script_name"
      ;;
    npm|*)
      run_step "$name" "npm run $script_name --silent"
      ;;
  esac
}

run_vitest_with_reporters() {
  local name="$1"
  local out_junit="$ARTIFACT_DIR/junit-${name}.xml"
  local out_json="$ARTIFACT_DIR/${name}-results.json"

  case "$RUNNER" in
    pnpm)
      run_step "$name" "pnpm vitest run --reporter=default --reporter=junit --reporter=json --outputFile.junit=$out_junit --outputFile.json=$out_json"
      ;;
    npm)
      run_step "$name" "npx vitest run --reporter=default --reporter=junit --reporter=json --outputFile.junit=$out_junit --outputFile.json=$out_json"
      ;;
    *)
      run_pkg_script test "$name"
      ;;
  esac
}

run_pytest() {
  local name="$1"
  local base_cmd=""
  local py_prefix=""
  if [[ -d src ]]; then
    py_prefix="PYTHONPATH=src "
  fi

  if command -v uv >/dev/null 2>&1 && [[ -f uv.lock ]]; then
    base_cmd="${py_prefix}uv run pytest"
  else
    base_cmd="${py_prefix}python3 -m pytest"
  fi

  run_step "$name" "$base_cmd --junitxml=$ARTIFACT_DIR/junit-${name}.xml"
}

run_unit() {
  local test_cmd=""
  if [[ "$has_pkg" == true ]]; then
    test_cmd="$(pkg_script_cmd test)"
  fi

  if [[ "$has_pkg" == true ]] && has_pkg_script test:artifacts:unit:raw; then
    run_pkg_script test:artifacts:unit:raw "unit"
  elif [[ -f pyproject.toml || -f pytest.ini || -f tox.ini ]]; then
    run_pytest "unit"
  elif [[ -n "$test_cmd" && "$test_cmd" == *vitest* ]]; then
    run_vitest_with_reporters "unit"
  elif [[ "$has_pkg" == true ]] && has_pkg_script test; then
    run_pkg_script test "unit"
  else
    echo "[test-with-artifacts] No unit test command found"
    return 0
  fi
}

run_integration() {
  if [[ "$has_pkg" == true ]] && has_pkg_script test:integration; then
    run_pkg_script test:integration "integration"
  else
    echo "[test-with-artifacts] No integration test command found, skipping"
  fi
}

run_e2e() {
  if [[ "$has_pkg" == true ]] && has_pkg_script test:e2e; then
    run_pkg_script test:e2e "e2e"
  elif [[ "$has_pkg" == true ]] && has_pkg_script test:e2e:web; then
    run_pkg_script test:e2e:web "e2e"
  else
    echo "[test-with-artifacts] No e2e test command found, skipping"
  fi
}

copy_discovered_artifacts() {
  local discovered="$ARTIFACT_DIR/discovered"
  mkdir -p "$discovered"

  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ "$file" == "$ARTIFACT_DIR"/* ]] && continue
    local out_name
    out_name="${file//\//__}"
    cp "$file" "$discovered/$out_name" 2>/dev/null || true
  done < <(rg --files -uuu . | rg -i '(junit.*\.xml|test-results.*\.(xml|json)|pytest.*\.xml|report.*\.xml|playwright.*\.xml|last-run\.json|blob-report.*\.json|test[-_]?output.*\.log)$')
}

build_manifest() {
  local manifest="$ARTIFACT_DIR/artifact-manifest.json"
  python3 <<PY
import json
from pathlib import Path
root = Path("$ARTIFACT_DIR")
files = []
for p in sorted(root.rglob('*')):
    if p.is_file():
        files.append({"path": str(p), "size": p.stat().st_size, "mtime": p.stat().st_mtime})
manifest = {"artifact_dir": str(root), "file_count": len(files), "files": files}
Path("$manifest").write_text(json.dumps(manifest, indent=2))
PY
}

case "$MODE" in
  all)
    run_unit || true
    run_integration || true
    run_e2e || true
    ;;
  unit)
    run_unit || true
    ;;
  integration)
    run_integration || true
    ;;
  e2e)
    run_e2e || true
    ;;
  *)
    echo "Usage: bash scripts/test-with-artifacts.sh [all|unit|integration|e2e]" >&2
    exit 2
    ;;
esac

copy_discovered_artifacts
build_manifest

echo "[test-with-artifacts] Artifacts written to $ARTIFACT_DIR"
if [[ "$overall_rc" -ne 0 ]]; then
  echo "[test-with-artifacts] One or more test steps failed; artifacts preserved for analysis"
fi

if [[ "$STRICT_ARTIFACTS" == "1" ]]; then
  exit "$overall_rc"
fi
exit 0
