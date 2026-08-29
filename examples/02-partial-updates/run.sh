#!/usr/bin/env bash
# POST vs PATCH: второй батч меняет значение у существующего объекта (POST)
# и добавляет новый (PATCH). Тип операции ds выбирает сам.
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

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/first.json"  --dt 1704067200
$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/second.json" --dt 1706745600
