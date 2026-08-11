#!/usr/bin/env bash
set -Eeuo pipefail
if ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
COMMANDS="$ROOT/contracts/verification.commands"
LOG_DIR="$ROOT/docs/evidence/local"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/verify-$STAMP.log"
mkdir -p "$LOG_DIR"
[[ -f "$COMMANDS" ]] || { echo "missing $COMMANDS" >&2; exit 2; }
exec > >(tee -a "$LOG") 2>&1
printf 'repository=%s\nstarted=%s\n' "$ROOT" "$(date --iso-8601=seconds)"
while IFS= read -r command || [[ -n "$command" ]]; do
  [[ -z "${command//[[:space:]]/}" ]] && continue
  [[ "$command" =~ ^[[:space:]]*# ]] && continue
  printf '\n>>> %s\n' "$command"
  bash -lc "cd \"$ROOT\" && $command"
done < "$COMMANDS"
printf '\ncompleted=%s\nlog=%s\n' "$(date --iso-8601=seconds)" "$LOG"
