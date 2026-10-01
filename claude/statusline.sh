#!/usr/bin/env bash
# Claude Code status line:  📁 path  [PONYTAIL]  ⎇ branch  ◆ Model
# Payload schema: https://code.claude.com/docs/en/statusline

input=$(cat)
dir=$(printf '%s' "$input"   | jq -r '.workspace.project_dir // .cwd // ""')
model=$(printf '%s' "$input" | jq -r '.model.display_name // .model.id // ""')
branch=$(git -C "$dir" branch --show-current 2>/dev/null)

GREEN=$'\033[38;5;108m'   # matches the ponytail plugin's own statusline colour
DIM=$'\033[2m'
RESET=$'\033[0m'

out="📁 ${dir}"

# ponytail mode flag. Semantics mirror the plugin's hooks/ponytail-statusline.sh:
# file absent = inactive, file present but empty = full.
flag="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.ponytail-active"
if [ -f "$flag" ]; then
    mode=$(head -n1 "$flag" | tr -d '[:space:]')
    case "$mode" in
        ''|full) tag="PONYTAIL" ;;
        *)       tag="PONYTAIL:$(printf '%s' "$mode" | tr '[:lower:]' '[:upper:]')" ;;
    esac
    out="${out}  ${GREEN}[${tag}]${RESET}"
fi

[ -n "$branch" ] && out="${out}  ⎇ ${branch}"
[ -n "$model" ]  && out="${out}  ${DIM}◆ ${model}${RESET}"

printf '%s' "$out"
