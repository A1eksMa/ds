#!/usr/bin/env bash
# Инвентарь показателей в source.json: type (справочно, для ds-loader/ds-webui) +
# archive (единственное поле из тройки type/archive/publish, на которое реагирует
# сам ds) -- internal_note грузится сразу в архив, минуя активную таблицу.
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

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch.json" --dt 1704067200

echo "--- ds get: internal_note НЕ в активной выборке (ушло сразу в архив при load) ---"
$DS --db "$DB" get --dt 1704067200 --src CRM

echo "--- ds get --archive: internal_note виден при явном запросе архива ---"
$DS --db "$DB" get --dt 1704067200 --src CRM --archive
