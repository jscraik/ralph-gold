#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
WORKSPACE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

usage() {
	cat <<'USAGE'
Usage:
  ./scripts/codex-preflight.sh [options]

Options:
  --stack <auto|repo|js|py|rust>    Stack mode. Default: auto
  --mode <off|optional|required>    Local Memory mode. Default: required
  --repo-fragment <text>            Require repo root to contain this fragment
  --bins <csv>                      Override required binaries
  --paths <csv>                     Override required paths
  -h, --help                        Show this help

Examples:
  ./scripts/codex-preflight.sh
  ./scripts/codex-preflight.sh --stack js
  ./scripts/codex-preflight.sh --stack py --mode optional
  ./scripts/codex-preflight.sh --repo-fragment local-memory

Legacy compatibility:
  ./scripts/codex-preflight.sh <repo-fragment> [bins-csv] [paths-csv]
  This preserves the older positional interface used by parent-repo checks and
  runs with Local Memory disabled unless the new flag-based mode is used.
USAGE
}

log_section() {
	printf '== %s ==\n' "$*"
}

log_ok() {
	printf '✅ %s\n' "$*"
}

log_warn() {
	printf '⚠️ %s\n' "$*"
}

log_err() {
	printf '❌ %s\n' "$*" >&2
}

extract_last_json_line() {
	local raw="${1:-}"
	printf '%s\n' "${raw}" | awk '/^\{/{line=$0} END{if (line != "") print line}'
}

extract_local_memory_rest_value() {
	local config_path="$1"
	local key="$2"
	awk -v wanted="${key}" '
		BEGIN { in_rest = 0 }
		/^[[:space:]]*rest_api:[[:space:]]*$/ { in_rest = 1; next }
		in_rest && /^[^[:space:]]/ { in_rest = 0 }
		in_rest && $1 == wanted ":" {
			sub(/^[^:]+:[[:space:]]*/, "", $0)
			gsub(/"/, "", $0)
			gsub(/[[:space:]]+#.*/, "", $0)
			gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
			print $0
			exit
		}
	' "${config_path}"
}


make_tmp_file() {
	mktemp "${TMPDIR:-/tmp}/local-memory-preflight.XXXXXX.json"
}

detect_stack() {
	if [[ -f package.json ]]; then
		echo js
		return
	fi
	if [[ -f pyproject.toml ]]; then
		echo py
		return
	fi
	if [[ -f Cargo.toml ]]; then
		echo rust
		return
	fi
	echo repo
}

stack_bins_csv() {
	case "$1" in
		js) echo 'git,bash,sed,rg,fd,node,npm,python3' ;;
		py) echo 'git,bash,sed,rg,fd,python3' ;;
		rust) echo 'git,bash,sed,rg,fd,python3,cargo' ;;
		repo) echo 'git,bash,sed,rg,fd,python3' ;;
		*) log_err "unknown stack: $1"; return 2 ;;
	esac
}

stack_paths_csv() {
	case "$1" in
		js) echo 'AGENTS.md,package.json,docs,docs/plans' ;;
		py) echo 'AGENTS.md,pyproject.toml,docs,docs/plans' ;;
		rust) echo 'AGENTS.md,Cargo.toml,docs,docs/plans' ;;
		repo) echo 'AGENTS.md,docs,docs/plans' ;;
		*) log_err "unknown stack: $1"; return 2 ;;
	esac
}

check_bins() {
	local bins_csv="$1"
	local -a bins=()
	local -a missing_bins=()
	local b

	IFS=',' read -r -a bins <<<"${bins_csv}"
	for b in "${bins[@]}"; do
		[[ -z "${b}" ]] && continue
		if ! command -v "${b}" >/dev/null 2>&1; then
			missing_bins+=("${b}")
		fi
	done

	if (( ${#missing_bins[@]} > 0 )); then
		log_err "missing binaries: ${missing_bins[*]}"
		return 2
	fi
	log_ok "binaries ok: ${bins_csv}"
}

check_paths() {
	local root="$1"
	local paths_csv="$2"
	local -a paths=()
	local p

	IFS=',' read -r -a paths <<<"${paths_csv}"
	for p in "${paths[@]}"; do
		[[ -z "${p}" ]] && continue

		local -a matches=()
		local match
		shopt -s nullglob
		for match in ${p}; do
			matches+=("${match}")
		done
		shopt -u nullglob

		if (( ${#matches[@]} == 0 )); then
			matches+=("${p}")
		fi

		local found=0
		local abs
		for match in "${matches[@]}"; do
			if [[ -e "${match}" ]]; then
				found=1
				if ! abs="$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "${match}")"; then
					log_err "failed to resolve path: ${match}"
					return 2
				fi
				if [[ "${abs}" != "${root}" && "${abs}" != "${root}"/* ]]; then
					log_err "path escapes repo root: ${match} -> ${abs}"
					return 2
				fi
			fi
		done

		if (( found == 0 )); then
			log_err "missing path: ${p}"
			return 2
		fi
	done
	log_ok "paths ok: ${paths_csv}"
}

preflight_local_memory_gold() {
	log_section "Local Memory Preflight"

	if ! command -v local-memory >/dev/null 2>&1; then
		log_err 'missing binary: local-memory'
		return 1
	fi
	if ! command -v jq >/dev/null 2>&1; then
		log_err 'missing binary: jq (required for local-memory checks)'
		return 1
	fi
	if ! command -v curl >/dev/null 2>&1; then
		log_err 'missing binary: curl (required for REST checks)'
		return 1
	fi

	local version
	version="$(local-memory --version 2>/dev/null | tr -d '\r')"
	echo "local-memory version: ${version}"

	local status_json
	if ! status_json="$(local-memory status --json 2>/dev/null)"; then
		log_err 'local-memory status failed'
		return 1
	fi
	status_json="$(extract_last_json_line "${status_json}")"
	if [[ -z "${status_json}" ]]; then
		log_err 'local-memory status returned no JSON payload'
		return 1
	fi

	local running
	running="$(echo "${status_json}" | jq -r '.data.running // .running // false')"

	local lm_config_path="${LOCAL_MEMORY_CONFIG_PATH:-${HOME}/.local-memory/config.yaml}"
	if [[ ! -f "${lm_config_path}" ]]; then
		log_err "local-memory config missing: ${lm_config_path}"
		echo '   Set LOCAL_MEMORY_CONFIG_PATH if your config lives elsewhere.' >&2
		return 1
	fi

	if ! rg -q '^[[:space:]]*host:[[:space:]]*"?127\.0\.0\.1"?([[:space:]]*#.*)?$' "${lm_config_path}"; then
		log_err 'local-memory config host policy failed: expected host: 127.0.0.1'
		echo "   file: ${lm_config_path}" >&2
		return 1
	fi
	if ! rg -q '^[[:space:]]*auto_port:[[:space:]]*false([[:space:]]*#.*)?$' "${lm_config_path}"; then
		log_err 'local-memory config auto_port policy failed: expected auto_port: false'
		echo "   file: ${lm_config_path}" >&2
		return 1
	fi
	log_ok "config host/auto_port policy ok: ${lm_config_path}"

	local rest_host
	rest_host="$(extract_local_memory_rest_value "${lm_config_path}" host)"
	rest_host="${rest_host:-127.0.0.1}"

	local rest_port
	rest_port="$(extract_local_memory_rest_value "${lm_config_path}" port)"
	rest_port="${rest_port:-3002}"
	if [[ ! "${rest_port}" =~ ^[0-9]+$ ]]; then
		log_err "invalid rest_api_port from config: ${rest_port}"
		return 1
	fi

	local health_url="http://${rest_host}:${rest_port}/api/v1/health"
	local health_json
	if [[ "${running}" != 'true' ]]; then
		if health_json="$(curl -fsS "${health_url}" 2>/dev/null)"; then
			if [[ "$(echo "${health_json}" | jq -r '.success // false')" == 'true' ]]; then
				log_warn "local-memory status reported stopped; REST health succeeded at ${health_url}"
				running='true'
			fi
		fi
	fi
	if [[ "${running}" != 'true' ]]; then
		log_err 'local-memory daemon is not running'
		return 1
	fi

	if ! health_json="$(curl -fsS "${health_url}")"; then
		log_err "REST health endpoint unreachable at ${health_url}"
		return 1
	fi
	if [[ "$(echo "${health_json}" | jq -r '.success // false')" != 'true' ]]; then
		log_err 'REST health endpoint returned success=false'
		return 1
	fi
	log_ok "REST health ok: ${health_url}"

	local probe
	probe="LM-PREFLIGHT-$(date +%Y%m%d-%H%M%S)-$$"
	local content_a="Preflight anchor ${probe}"
	local content_b="Preflight evidence ${probe}"

	local observe_a_json
	local observe_b_json
	observe_a_json="$(local-memory observe "${content_a}" --domain 'coding-harness' --tags 'preflight,local-memory' --source 'codex_preflight' --json 2>/dev/null)" || {
		log_err 'observe A failed'
		return 1
	}
	observe_b_json="$(local-memory observe "${content_b}" --domain 'coding-harness' --tags 'preflight,local-memory' --source 'codex_preflight' --json 2>/dev/null)" || {
		log_err 'observe B failed'
		return 1
	}
	observe_a_json="$(extract_last_json_line "${observe_a_json}")"
	observe_b_json="$(extract_last_json_line "${observe_b_json}")"

	local id_a
	local id_b
	id_a="$(echo "${observe_a_json}" | jq -r '.id // .data.id // .memory_id // .data.memory_id // empty')"
	id_b="$(echo "${observe_b_json}" | jq -r '.id // .data.id // .memory_id // .data.memory_id // empty')"
	if [[ -z "${id_a}" || -z "${id_b}" ]]; then
		log_err 'observe returned no memory IDs'
		return 1
	fi

	local relate_json
	relate_json="$(local-memory relate "${id_a}" "${id_b}" --type 'references' --strength 0.8 --confirm --json 2>/dev/null)" || {
		log_err 'relate failed'
		return 1
	}
	relate_json="$(extract_last_json_line "${relate_json}")"
	local relationship_id
	relationship_id="$(echo "${relate_json}" | jq -r '.id // .data.id // .relationship_id // .data.relationship_id // empty')"
	local relate_ok
	relate_ok="$(echo "${relate_json}" | jq -r '.success // true')"
	if [[ "${relate_ok}" != 'true' ]]; then
		log_err 'relate reported failure'
		return 1
	fi

	local search_json
	search_json="$(local-memory search "${probe}" --limit 10 --json 2>/dev/null)" || {
		log_err 'search failed'
		return 1
	}
	search_json="$(extract_last_json_line "${search_json}")"
	local search_hits
	search_hits="$(echo "${search_json}" | jq -r '
		if type == "array" then length
		elif .results then (.results | length)
		elif .data.results then (.data.results | length)
		elif .data then (.data | length)
		else 0 end
	')"
	if [[ "${search_hits}" -lt 1 ]]; then
		log_err "search returned no results for probe ${probe}"
		return 1
	fi
	log_ok "smoke cycle ok: ids ${id_a}, ${id_b}; relationship ${relationship_id}"

	# Cleanup: delete probe memories to prevent junk accumulation in the store.
	local-memory delete "${id_a}" --json >/dev/null 2>&1 || log_warn "cleanup: failed to delete probe memory ${id_a}"
	local-memory delete "${id_b}" --json >/dev/null 2>&1 || log_warn "cleanup: failed to delete probe memory ${id_b}"
	log_ok "cleanup ok: probe memories deleted"

	local malformed_output dup_output_1 dup_output_2
	malformed_output="$(make_tmp_file)"
	dup_output_1="$(make_tmp_file)"
	dup_output_2="$(make_tmp_file)"
	trap 'rm -f "${malformed_output}" "${dup_output_1}" "${dup_output_2}"' RETURN

	local malformed_code
	malformed_code="$(curl -sS -o "${malformed_output}" -w '%{http_code}' \
		-H 'Content-Type: application/json' \
		-d '{"level":"observation"}' \
		"http://${rest_host}:${rest_port}/api/v1/observe")"
	if [[ "${malformed_code}" -lt 400 ]]; then
		trap - RETURN
		rm -f "${malformed_output}" "${dup_output_1}" "${dup_output_2}"
		log_err "malformed payload did not return an error (HTTP ${malformed_code})"
		return 1
	fi
	log_ok "malformed payload rejected: HTTP ${malformed_code}"

	local dup_payload
	dup_payload="$(jq -nc --arg c "${content_a}" '{content:$c,domain:"coding-harness",source:"codex_preflight",tags:["preflight","duplicate-check"]}')"
	local dup_code_1
	local dup_code_2
	dup_code_1="$(curl -sS -o "${dup_output_1}" -w '%{http_code}' \
		-H 'Content-Type: application/json' \
		-d "${dup_payload}" \
		"http://${rest_host}:${rest_port}/api/v1/observe")"
	dup_code_2="$(curl -sS -o "${dup_output_2}" -w '%{http_code}' \
		-H 'Content-Type: application/json' \
		-d "${dup_payload}" \
		"http://${rest_host}:${rest_port}/api/v1/observe")"
	echo "ℹ️ duplicate behavior snapshot: first=${dup_code_1}, second=${dup_code_2}"

	local daemon_log="${HOME}/.local-memory/daemon.log"
	if [[ -f "${daemon_log}" ]]; then
		local migration_line
		migration_line="$(tail -n 300 "${daemon_log}" | rg -n '"pending_migrations"|"target_version"|"current_version"' -m 1 || true)"
		if [[ -n "${migration_line}" ]]; then
			echo 'ℹ️ migration status signal found in daemon log'
		else
			log_warn 'no migration status signal found in recent daemon log tail'
		fi
	else
		log_warn "daemon log not found at ${daemon_log}"
	fi

	trap - RETURN
	rm -f "${malformed_output}" "${dup_output_1}" "${dup_output_2}"
	log_ok 'local-memory preflight passed'
}

main() {
	local stack='auto'
	local local_memory_mode='required'
	local expected_repo=''
	local bins_csv=''
	local paths_csv=''

	if (( $# > 0 )) && [[ "${1}" != --* ]] && [[ "${1}" != '-h' ]]; then
		if (( $# > 3 )); then
			log_err "legacy positional mode accepts at most 3 arguments"
			usage >&2
			return 2
		fi
		expected_repo="${1:-}"
		bins_csv="${2:-}"
		paths_csv="${3:-}"
		local_memory_mode='off'
		set --
	fi

	while (( $# > 0 )); do
		case "$1" in
			--stack)
				stack="${2:-}"
				shift 2
				;;
			--mode)
				local_memory_mode="${2:-}"
				shift 2
				;;
			--repo-fragment)
				expected_repo="${2:-}"
				shift 2
				;;
			--bins)
				bins_csv="${2:-}"
				shift 2
				;;
			--paths)
				paths_csv="${2:-}"
				shift 2
				;;
			-h|--help)
				usage
				return 0
				;;
			*)
				log_err "unknown argument: $1"
				usage >&2
				return 2
				;;
		esac
	done

	case "${local_memory_mode}" in
		off|optional|required) ;;
		*) log_err "invalid --mode: ${local_memory_mode}"; return 2 ;;
	esac

	log_section 'Codex Preflight'
	echo "pwd: $(pwd)"

	if ! command -v git >/dev/null 2>&1; then
		log_err 'missing binary: git'
		return 2
	fi

	local git_root
	if ! git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
		log_err 'not inside a git repo (git rev-parse failed)'
		return 2
	fi
	if [[ -z "${git_root}" ]]; then
		log_err 'git rev-parse returned empty root'
		return 2
	fi
	git_root="$(cd -- "${git_root}" && pwd -P)"
	echo "git root: ${git_root}"
	echo "workspace root: ${WORKSPACE_ROOT}"

	if [[ "${WORKSPACE_ROOT}" != "${git_root}" && "${WORKSPACE_ROOT}" != "${git_root}"/* ]]; then
		log_err "script workspace mismatch: ${WORKSPACE_ROOT} is not inside git root ${git_root}"
		return 2
	fi
	if [[ -n "${expected_repo}" && "${WORKSPACE_ROOT}" != *"${expected_repo}"* ]]; then
		log_err "repo mismatch: expected fragment '${expected_repo}' in '${WORKSPACE_ROOT}'"
		return 2
	fi

	cd "${WORKSPACE_ROOT}"

	if [[ "${stack}" == 'auto' ]]; then
		stack="$(detect_stack)"
	fi
	echo "stack: ${stack}"

	if [[ -z "${bins_csv}" ]]; then
		bins_csv="$(stack_bins_csv "${stack}")"
	fi
	if [[ "${local_memory_mode}" != 'off' ]]; then
		bins_csv="${bins_csv},jq,curl"
	fi
	if [[ -z "${paths_csv}" ]]; then
		paths_csv="$(stack_paths_csv "${stack}")"
	fi

	check_bins "${bins_csv}"
	check_paths "${WORKSPACE_ROOT}" "${paths_csv}"

	echo "git branch: $(git -C "${WORKSPACE_ROOT}" rev-parse --abbrev-ref HEAD)"
	echo "clean?: $(git -C "${WORKSPACE_ROOT}" status --porcelain -- . | wc -l | tr -d ' ') changes"

	if [[ "${local_memory_mode}" != 'off' ]]; then
		if ! preflight_local_memory_gold; then
			if [[ "${local_memory_mode}" == 'required' ]]; then
				log_err 'local-memory preflight failed (required mode)'
				return 2
			fi
			log_warn 'local-memory preflight failed (optional mode)'
		fi
	fi

	log_ok 'preflight passed'
}

preflight_repo() {
	local expected_repo="${1:-}"
	local bins_csv="${2:-}"
	local paths_csv="${3:-}"
	local -a wrapper_args=(--stack repo --mode off)
	if (( $# > 0 )) && [[ "${1}" != --* ]] && [[ "${1}" != '-h' ]]; then
		wrapper_args+=(--repo-fragment "${expected_repo}")
		if [[ -n "${bins_csv}" ]]; then
			wrapper_args+=(--bins "${bins_csv}")
		fi
		if [[ -n "${paths_csv}" ]]; then
			wrapper_args+=(--paths "${paths_csv}")
		fi
		if main "${wrapper_args[@]}"; then
			return 0
		else
			return $?
		fi
	fi
	if main "${wrapper_args[@]}" "$@"; then
		return 0
	else
		return $?
	fi
}

preflight_js() {
	local expected_repo="${1:-}"
	local bins_csv="${2:-}"
	local paths_csv="${3:-}"
	local -a wrapper_args=(--stack js --mode off)
	if (( $# > 0 )) && [[ "${1}" != --* ]] && [[ "${1}" != '-h' ]]; then
		wrapper_args+=(--repo-fragment "${expected_repo}")
		if [[ -n "${bins_csv}" ]]; then
			wrapper_args+=(--bins "${bins_csv}")
		fi
		if [[ -n "${paths_csv}" ]]; then
			wrapper_args+=(--paths "${paths_csv}")
		fi
		if main "${wrapper_args[@]}"; then
			return 0
		else
			return $?
		fi
	fi
	if main "${wrapper_args[@]}" "$@"; then
		return 0
	else
		return $?
	fi
}

preflight_py() {
	local expected_repo="${1:-}"
	local bins_csv="${2:-}"
	local paths_csv="${3:-}"
	local -a wrapper_args=(--stack py --mode off)
	if (( $# > 0 )) && [[ "${1}" != --* ]] && [[ "${1}" != '-h' ]]; then
		wrapper_args+=(--repo-fragment "${expected_repo}")
		if [[ -n "${bins_csv}" ]]; then
			wrapper_args+=(--bins "${bins_csv}")
		fi
		if [[ -n "${paths_csv}" ]]; then
			wrapper_args+=(--paths "${paths_csv}")
		fi
		if main "${wrapper_args[@]}"; then
			return 0
		else
			return $?
		fi
	fi
	if main "${wrapper_args[@]}" "$@"; then
		return 0
	else
		return $?
	fi
}

preflight_rust() {
	local expected_repo="${1:-}"
	local bins_csv="${2:-}"
	local paths_csv="${3:-}"
	local -a wrapper_args=(--stack rust --mode off)
	if (( $# > 0 )) && [[ "${1}" != --* ]] && [[ "${1}" != '-h' ]]; then
		wrapper_args+=(--repo-fragment "${expected_repo}")
		if [[ -n "${bins_csv}" ]]; then
			wrapper_args+=(--bins "${bins_csv}")
		fi
		if [[ -n "${paths_csv}" ]]; then
			wrapper_args+=(--paths "${paths_csv}")
		fi
		if main "${wrapper_args[@]}"; then
			return 0
		else
			return $?
		fi
	fi
	if main "${wrapper_args[@]}" "$@"; then
		return 0
	else
		return $?
	fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi
