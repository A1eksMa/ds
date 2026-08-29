#!/usr/bin/env bash
# ds get: свёртка журнала в состояние источника на заданную дату.
# Грузим те же два батча, что в 01, затем выгружаем состояние на 2024-02-01.
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

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch_2024-01.json" --dt 1704067200
$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch_2024-02.json" --dt 1706745600

echo "--- ds get --dt 1706745600 ---"
$DS --db "$DB" get --dt 1706745600

echo "--- ds get --dt 1704067200 --lb email (машина времени) ---"
$DS --db "$DB" get --dt 1704067200 --lb email
