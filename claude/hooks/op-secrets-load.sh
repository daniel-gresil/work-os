#!/usr/bin/env bash
#
# op-secrets-load.sh — batch-fetch secrets from 1Password into a session-local
# cache file. Run at the start of every Claude Code session in a repo whose
# `.claude/op-secrets.txt` lists secrets the session may need. Single
# biometric prompt (or zero, while 1P's unlock window is open) for all of them.
#
# Usage:
#   ~/.claude/op-secrets-load.sh                      # uses ./.claude/op-secrets.txt
#   ~/.claude/op-secrets-load.sh /path/to/manifest    # explicit manifest
#
# After running, source the cache file:
#   source ~/.cache/claude-secrets/<repo-name>/env.sh
#
# Cache files are mode 600. Multi-line values (e.g., SSH private keys) are
# written to per-secret files and exposed as env vars holding their paths.
#
# Manifest format (.claude/op-secrets.txt) — one entry per line:
#   ENV_NAME = op://vault/item/field @ account              # simple value
#   FILE:ENV_NAME = op://vault/item/field @ account         # multi-line/binary
# Comments (#) and blank lines are ignored.

set -euo pipefail

MANIFEST="${1:-$(pwd)/.claude/op-secrets.txt}"
if [ ! -f "$MANIFEST" ]; then
  echo "op-secrets-load: no manifest at $MANIFEST (skip)" >&2
  exit 0
fi

REPO_ROOT="$(git -C "$(dirname "$MANIFEST")" rev-parse --show-toplevel 2>/dev/null || dirname "$(dirname "$MANIFEST")")"
REPO_NAME="$(basename "$REPO_ROOT")"
CACHE_DIR="$HOME/.cache/claude-secrets/$REPO_NAME"
ENV_FILE="$CACHE_DIR/env.sh"

mkdir -p "$CACHE_DIR/files"
chmod 700 "$CACHE_DIR"

# Write to a tempfile first; only atomically replace $ENV_FILE on success.
# That way a stalled / killed run doesn't leave $ENV_FILE empty for the
# rest of the session.
ENV_FILE_TMP="$(mktemp "$CACHE_DIR/env.sh.XXXXXX")"
chmod 600 "$ENV_FILE_TMP"
trap 'rm -f "$ENV_FILE_TMP"' EXIT

# Header so a stale cache is identifiable
{
  echo "# Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) by op-secrets-load.sh"
  echo "# Source: $MANIFEST"
} >> "$ENV_FILE_TMP"

FAIL=0
COUNT=0
while IFS= read -r raw || [ -n "$raw" ]; do
  line="${raw%%#*}"
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [ -z "$line" ] && continue

  # Parse: [FILE:]ENV_NAME = op://...path-which-may-contain-spaces... [@ account]
  # Split on " = " first (env name on left), then optional " @ account" on right.
  if [[ "$line" =~ ^(FILE:)?([A-Z_][A-Z0-9_]*)[[:space:]]*=[[:space:]]*(.+)$ ]]; then
    IS_FILE="${BASH_REMATCH[1]}"
    ENV_NAME="${BASH_REMATCH[2]}"
    REMAINDER="${BASH_REMATCH[3]}"
    # If remainder ends with " @ account", split it off
    ACCOUNT=""
    if [[ "$REMAINDER" =~ ^(.+)[[:space:]]@[[:space:]]([^[:space:]]+)[[:space:]]*$ ]]; then
      OP_REF="${BASH_REMATCH[1]}"
      ACCOUNT="${BASH_REMATCH[2]}"
      # Trim trailing whitespace from OP_REF (op paths don't have trailing spaces)
      OP_REF="${OP_REF%"${OP_REF##*[![:space:]]}"}"
    else
      OP_REF="${REMAINDER%"${REMAINDER##*[![:space:]]}"}"
    fi
    # Sanity: must look like an op:// ref
    if [[ ! "$OP_REF" =~ ^op:// ]]; then
      echo "  WARN value isn't an op:// ref: $line" >&2
      continue
    fi
    OP_ARGS=()
    [ -n "$ACCOUNT" ] && OP_ARGS+=("--account" "$ACCOUNT")

    if VALUE=$(op read "${OP_ARGS[@]}" "$OP_REF" 2>"$CACHE_DIR/.op-error"); then
      if [ -n "$IS_FILE" ]; then
        FILE_PATH="$CACHE_DIR/files/$ENV_NAME"
        # Append a trailing newline — OpenSSH private keys (and most text-format
        # secrets) require it. printf '%s' alone strips trailing newlines from
        # op's output and ssh-keygen rejects the resulting file as malformed.
        printf '%s\n' "$VALUE" > "$FILE_PATH"
        chmod 600 "$FILE_PATH"
        printf 'export %s=%q\n' "$ENV_NAME" "$FILE_PATH" >> "$ENV_FILE_TMP"
      else
        printf 'export %s=%q\n' "$ENV_NAME" "$VALUE" >> "$ENV_FILE_TMP"
      fi
      COUNT=$((COUNT + 1))
      echo "  loaded $ENV_NAME${IS_FILE:+ (file)}" >&2
    else
      echo "  FAILED $OP_REF (skipped): $(head -1 "$CACHE_DIR/.op-error" 2>/dev/null)" >&2
      FAIL=$((FAIL + 1))
    fi
  else
    echo "  WARN unparseable line: $line" >&2
  fi
done < "$MANIFEST"

# Only swap into place if at least one secret loaded — a fully-failed run
# preserves whatever cache was there before (defensive against biometric
# timeouts that would otherwise blank the cache mid-session).
if [ "$COUNT" -gt 0 ]; then
  mv "$ENV_FILE_TMP" "$ENV_FILE"
  trap - EXIT
  echo "op-secrets-load: $COUNT loaded${FAIL:+, $FAIL failed} → $ENV_FILE" >&2
  echo "$ENV_FILE"
else
  echo "op-secrets-load: 0 loaded${FAIL:+, $FAIL failed} — keeping previous $ENV_FILE (if any)" >&2
  exit 1
fi
