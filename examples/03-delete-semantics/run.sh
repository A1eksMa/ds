#!/usr/bin/env bash
# Семантика удаления: phone задаётся, затем приходит null (DELETE),
# затем снова задаётся (PATCH — повторное появление после удаления).
# Использование:  bash run.sh [WORKDIR]   (env DS — переопределение команды)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${1:-$(mktemp -d)}"
DB="$WORK/data.db"
DS="${DS:-python3 -m src.cli.commands}"

cd "$REPO"
export PYTHONPATH="$REPO"
echo "workdir: $WORK" >&2

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/step1-create.json"       --dt 1704067200
$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/step2-delete-phone.json" --dt 1705276800
$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/step3-phone-again.json"  --dt 1706745600
