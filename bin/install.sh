#!/usr/bin/env bash
# install.sh — Install the grit skill into AI coding tool skill directories.
#
# Default behaviour (no flags): installs into whichever tool directories
# already exist on this machine. If none exist, prints a hint and exits.
#
# Examples:
#   bin/install.sh                              # auto-detect installed tools
#   bin/install.sh --zrb                        # zrb only (convenience)
#   bin/install.sh --claude                     # Claude Code only (convenience)
#   bin/install.sh --tools codex,opencode       # specific tools (creates dirs)
#   bin/install.sh --tools all                  # all known tools
#   bin/install.sh --all                        # alias for --tools all
#   bin/install.sh --no-hook                    # skill only, skip hook wiring
#   bin/install.sh --uninstall --tools all      # remove grit from all tools
#   bin/install.sh --dry-run --tools cursor     # preview without changing anything
#
# THE SKILL is runtime-neutral and installs to every target as
# <dotdir>/skills/grit/.
#
# THE HOOK is not. It needs a PreToolUse mechanism, which only some runtimes
# have, so it is wired only where one exists:
#   claude -> ~/.claude/settings.json   (nested "hooks" block)
#   zrb    -> ~/.zrb/hooks.json         (zrb's native array format)
# Everywhere else the skill still works; you just lose the once-per-session
# prompt and the authorship record. The installer says so rather than pretending.
#
# Your measured profile always lives in ~/.grit, whatever runtime you use —
# proficiency belongs to the person, not the tool and not the repo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_SRC="${REPO_ROOT}/skills/grit"
HOOK_SRC="${REPO_ROOT}/hooks/grit-hook.py"

# ---------------------------------------------------------------------------
# Tool registry — maps tool IDs to their skills directory under $HOME.
# Uses a case function rather than associative arrays (bash 3.2 compat).
# ---------------------------------------------------------------------------
tool_dir() {
    case "$1" in
        zrb)            echo "${HOME}/.zrb/skills" ;;
        claude)         echo "${HOME}/.claude/skills" ;;
        codex)          echo "${HOME}/.codex/skills" ;;
        opencode)       echo "${HOME}/.opencode/skills" ;;
        cursor)         echo "${HOME}/.cursor/skills" ;;
        windsurf)       echo "${HOME}/.windsurf/skills" ;;
        github-copilot) echo "${HOME}/.github/skills" ;;
        gemini)         echo "${HOME}/.gemini/skills" ;;
        amazon-q)       echo "${HOME}/.amazonq/skills" ;;
        cline)          echo "${HOME}/.cline/skills" ;;
        codebuddy)      echo "${HOME}/.codebuddy/skills" ;;
        continue)       echo "${HOME}/.continue/skills" ;;
        crush)          echo "${HOME}/.crush/skills" ;;
        factory)        echo "${HOME}/.factory/skills" ;;
        iflow)          echo "${HOME}/.iflow/skills" ;;
        junie)          echo "${HOME}/.junie/skills" ;;
        kilocode)       echo "${HOME}/.kilocode/skills" ;;
        kiro)           echo "${HOME}/.kiro/skills" ;;
        lingma)         echo "${HOME}/.lingma/skills" ;;
        pi)             echo "${HOME}/.pi/skills" ;;
        qoder)          echo "${HOME}/.qoder/skills" ;;
        qwen)           echo "${HOME}/.qwen/skills" ;;
        roocode)        echo "${HOME}/.roo/skills" ;;
        antigravity)    echo "${HOME}/.agent/skills" ;;
        bob)            echo "${HOME}/.bob/skills" ;;
        costrict)       echo "${HOME}/.cospec/skills" ;;
        forgecode)      echo "${HOME}/.forge/skills" ;;
        kimi)           echo "${HOME}/.kimi/skills" ;;
        trae)           echo "${HOME}/.trae/skills" ;;
        vibe)           echo "${HOME}/.vibe/skills" ;;
        auggie)         echo "${HOME}/.augment/skills" ;;
        *)              return 1 ;;
    esac
}

known_tool() { tool_dir "$1" > /dev/null 2>&1; }

# Ordered list for usage display and --tools all.
TOOL_IDS=(
    zrb claude codex opencode cursor windsurf github-copilot
    gemini amazon-q cline codebuddy continue crush factory iflow
    junie kilocode kiro lingma pi qoder qwen roocode
    antigravity bob costrict forgecode kimi trae vibe auggie
)

uninstall=0
dry_run=0
doctor=0
here=0
with_hook=1
want_tool=()

want() {
    local id="$1" x
    for x in "${want_tool[@]:-}"; do
        [[ "$x" == "$id" ]] && return 0
    done
    return 1
}

usage() {
    cat <<'EOF'
Usage: install.sh [options]

Options:
  --zrb               Target ~/.zrb/skills/
  --claude            Target ~/.claude/skills/
  --tools <id,...>    Target specific tools by ID (comma-separated).
                      Use "all" for every known tool.
  --all               Alias for --tools all
  --no-hook           Install the skill only; do not wire the PreToolUse hook
  --here              Install into THIS directory only (project-scoped, no ~ changes)
  --doctor            Report every grit hook registration and whether it works
  --uninstall         Remove grit from selected targets
  --dry-run           Print what would happen without changing anything
  -h, --help          This message

With no target flags, install.sh installs to whichever tool directories
already exist on this machine. If none exist, it exits with a hint.

The hook is only wired for runtimes that have a PreToolUse mechanism
(claude, zrb). Elsewhere the skill installs and works without it.
EOF
}

log() { printf '[install.sh] %s\n' "$*"; }

run() {
    if [[ "${dry_run}" -eq 1 ]]; then
        printf '[dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --zrb)       want_tool+=("zrb") ;;
        --claude)    want_tool+=("claude") ;;
        --all)       want_tool=("${TOOL_IDS[@]}") ;;
        --no-hook)   with_hook=0 ;;
        --tools)
            shift
            if [[ $# -eq 0 ]]; then
                log "Missing value for --tools"; usage; exit 2
            fi
            if [[ "$1" == "all" ]]; then
                want_tool=("${TOOL_IDS[@]}")
            else
                IFS=',' read -ra ids <<< "$1"
                for id in "${ids[@]}"; do
                    id="${id#"${id%%[![:space:]]*}"}"
                    id="${id%"${id##*[![:space:]]}"}"
                    if ! known_tool "${id}"; then
                        log "Unknown tool ID: ${id}"; exit 2
                    fi
                    want_tool+=("${id}")
                done
            fi
            ;;
        --uninstall) uninstall=1 ;;
        --doctor)    doctor=1 ;;
        --here)      here=1 ;;
        --dry-run)   dry_run=1 ;;
        -h|--help)   usage; exit 0 ;;
        *)           log "Unknown option: $1"; usage; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# --doctor: find every registration anywhere and check it actually runs.
# A hook whose script is missing exits 2, which both runtimes read as "block",
# so a stale path does not degrade — it stops every file write in that project.
# ---------------------------------------------------------------------------
if [[ "${doctor}" -eq 1 ]]; then
    python3 "${SKILL_SRC}/doctor.py" "$(pwd)"
    exit $?
fi

# ---------------------------------------------------------------------------
# --here: project-scoped install into the current directory, absolute paths
# filled in by us. Replaces the copy-paste snippet that shipped a placeholder.
# ---------------------------------------------------------------------------
if [[ "${here}" -eq 1 ]]; then
    target="$(pwd)"
    if [[ "${uninstall}" -eq 1 ]]; then
        run python3 "${SCRIPT_DIR}/_wire_hook.py" zrb "${target}/.zrb/hooks.json" \
            "${HOOK_SRC}" remove
        run rm -f "${target}/.claude/skills/grit"
        run rmdir "${target}/.claude/skills" "${target}/.claude" "${target}/.zrb" 2>/dev/null || true
        log "removed project-scoped install from ${target}"
        exit 0
    fi
    run mkdir -p "${target}/.claude/skills"
    run ln -sfn "${SKILL_SRC}" "${target}/.claude/skills/grit"
    run python3 "${SCRIPT_DIR}/_wire_hook.py" zrb "${target}/.zrb/hooks.json" \
        "${HOOK_SRC}" install
    log "project-scoped install in ${target}"

    # Verify what we just wrote, same as a full install does. --here used to
    # exit before the checks, which is how a project-scoped install could
    # report success and be wired to nothing.
    if [[ "${dry_run}" -eq 0 ]]; then
        python3 "${SKILL_SRC}/doctor.py" "${target}" >/dev/null 2>&1 \
            && log "verify: registrations ok" \
            || log "verify: FAILED — run python3 ${SKILL_SRC}/doctor.py"
    fi

    # Scoring reads authorship out of `git diff`. Without a repository
    # verify_edit.py cannot snapshot, every task comes back UNVERIFIED, and
    # nothing can ever score — silently. Say so now rather than let someone
    # discover it after doing the work.
    if ! git -C "${target}" rev-parse --git-dir >/dev/null 2>&1; then
        echo
        log "NOTE: ${target} is not a git repository."
        log "  Authorship is still recorded, but nothing can be SCORED:"
        log "  verify_edit.py needs a git diff to tell your work from mine."
        log "  Fix with:  git init"
    fi

    echo
    log "zrb also needs: export ZRB_LLM_EXTRA_SKILL_DIRS=\"${SKILL_SRC%/grit}\""
    log "Claude Code picks up .claude/skills/grit automatically."
    exit 0
fi

# ---------------------------------------------------------------------------
# Auto-detect: if no tool flags given, target tools whose home dir exists.
# ---------------------------------------------------------------------------
if [[ "${#want_tool[@]}" -eq 0 ]]; then
    detected=0
    for id in "${TOOL_IDS[@]}"; do
        parent_dir="$(dirname "$(tool_dir "${id}")")"
        if [[ -d "${parent_dir}" ]]; then
            want_tool+=("${id}")
            detected=1
        fi
    done
    if [[ "${detected}" -eq 0 ]]; then
        log "No tool home directories detected."
        log "Re-run with --tools <id,...> or --all to install to specific tools."
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Source validation
# ---------------------------------------------------------------------------
[[ -d "${SKILL_SRC}" ]] || { log "Skill source not found at ${SKILL_SRC}"; exit 1; }
[[ -f "${HOOK_SRC}" ]]  || { log "Hook source not found at ${HOOK_SRC}"; exit 1; }

# ---------------------------------------------------------------------------
# Hook wiring. Only for runtimes that have a PreToolUse mechanism.
#
# zrb reads ~/.claude/settings.json for Claude compatibility as well as its own
# hooks.json, so registering in both would fire the hook twice on one edit. The
# hook itself de-duplicates within a 2-second window, which makes that safe —
# but we still register natively per runtime so each works standalone.
# ---------------------------------------------------------------------------
hook_dest_dir() {
    case "$1" in
        claude) echo "${HOME}/.claude/hooks/grit" ;;
        zrb)    echo "${HOME}/.zrb/hooks/grit" ;;
        *)      return 1 ;;
    esac
}

wire_hook() {
    local id="$1" action="$2"
    local dest; dest="$(hook_dest_dir "${id}")" || return 0

    if [[ "${action}" == "install" ]]; then
        run mkdir -p "${dest}"
        run cp "${HOOK_SRC}" "${dest}/grit-hook.py"
        run chmod +x "${dest}/grit-hook.py"
    else
        run rm -rf "${dest}"
    fi

    if [[ "${dry_run}" -eq 1 ]]; then
        printf '[dry-run] register %s hook (%s)\n' "${id}" "${action}"
        return 0
    fi

    case "${id}" in
        claude) python3 "${SCRIPT_DIR}/_wire_hook.py" claude \
                    "${HOME}/.claude/settings.json" \
                    "${dest}/grit-hook.py" "${action}" ;;
        zrb)    python3 "${SCRIPT_DIR}/_wire_hook.py" zrb \
                    "${HOME}/.zrb/hooks.json" \
                    "${dest}/grit-hook.py" "${action}" ;;
    esac
}

# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------
install_to() {
    local id="$1" target="$2" dest="$2/grit"
    log "Target: ${target}"
    run mkdir -p "${target}"
    # Replace wholesale: a glob-copy leaves files from an older layout behind,
    # and a stale asset is worse than a missing one — it loads, and it is wrong.
    [[ -e "${dest}" ]] && run rm -rf "${dest}"
    run cp -R "${SKILL_SRC}" "${dest}"
    run rm -rf "${dest}/__pycache__"
    log "  installed grit"
    if [[ "${with_hook}" -eq 1 ]]; then
        if hook_dest_dir "${id}" >/dev/null 2>&1; then
            wire_hook "${id}" install
        else
            log "  no hook — ${id} has no PreToolUse mechanism (skill still works)"
        fi
    fi
}

uninstall_from() {
    local id="$1" target="$2" dest="$2/grit"
    log "Target: ${target} (uninstall)"
    if [[ -e "${dest}" ]]; then
        run rm -rf "${dest}"
        log "  removed grit"
    else
        log "  nothing to remove"
    fi
    hook_dest_dir "${id}" >/dev/null 2>&1 && wire_hook "${id}" remove
    run rmdir "${target}" 2>/dev/null || true
}

for id in "${TOOL_IDS[@]}"; do
    if want "${id}"; then
        if [[ "${uninstall}" -eq 1 ]]; then
            uninstall_from "${id}" "$(tool_dir "${id}")"
        else
            install_to "${id}" "$(tool_dir "${id}")"
        fi
    fi
done

# ---------------------------------------------------------------------------
# Verify what we installed actually runs. Asserting it would be the exact
# failure this project exists to argue against.
# ---------------------------------------------------------------------------
if [[ "${uninstall}" -eq 0 && "${dry_run}" -eq 0 ]]; then
    if python3 -B "${SKILL_SRC}/test_serve.py" >/dev/null 2>&1; then
        log "verify: daemon self-check passed"
    else
        log "verify: FAILED — run python3 ${SKILL_SRC}/test_serve.py"; exit 1
    fi
    if python3 -B "${SKILL_SRC}/score.py" selftest >/dev/null 2>&1; then
        log "verify: scoring self-check passed"
    else
        log "verify: FAILED — run python3 ${SKILL_SRC}/score.py selftest"; exit 1
    fi
    if python3 -B "${REPO_ROOT}/bin/check_docs.py" >/dev/null 2>&1; then
        log "verify: docs match the code"
    else
        log "verify: docs drifted — run python3 ${REPO_ROOT}/bin/check_docs.py" >&2
    fi
    if [[ "${with_hook}" -eq 1 ]]; then
        if python3 -B "${REPO_ROOT}/hooks/test_hook.py" >/dev/null 2>&1; then
            log "verify: hook self-check passed"
        else
            log "verify: FAILED — run python3 ${REPO_ROOT}/hooks/test_hook.py"; exit 1
        fi
    fi
fi

log "Done."

if [[ "${uninstall}" -eq 0 && "${dry_run}" -eq 0 ]]; then
    cat <<EOF

Restart your assistant, then ask it "what's my grit standing?" — or just start
work, and the hook offers you the choice the first time it reaches for an editor.

  Dashboard:  python3 ~/.claude/skills/grit/serve.py   (or any target's copy)
              it prints its URL (default :7801) — first run asks you to pick a theme

  Off switch: touch .grit/off   in a project
              GRIT_OFF=1        everywhere
              bin/install.sh --uninstall --tools all
EOF
fi
