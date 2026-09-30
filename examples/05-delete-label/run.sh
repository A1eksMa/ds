#!/usr/bin/env bash
# Жёсткое удаление показателя: `ds delete` физически убирает транзакции из
# журнала -- в отличие от DELETE-акта (val=null, см. 03-delete-semantics),
# после которого запись остаётся в журнале как отметка "удалено".
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

echo "--- ds get: junk_field ещё на месте ---"
$DS --db "$DB" get --dt 1704067200 --src CRM

echo "--- ds delete --src CRM --lb junk_field --yes ---"
$DS --db "$DB" delete --src CRM --lb junk_field --yes

echo "--- ds get: junk_field пропал из данных (метка в пуле осталась, но пуста) ---"
$DS --db "$DB" get --dt 1704067200 --src CRM
