#!/usr/bin/env bash
# `ds archive --where LB=VALUE`: находит все ключи, у которых ТЕКУЩЕЕ (свёрнутое,
# Level 1) значение показателя LB равно VALUE, и архивирует у них ВСЕ показатели
# (не только LB) -- ровно кейс "признак is_test_account=true -> в архив целиком".
# `ds delete` понимает тот же --where (и весь остальной набор селекторов —
# --lb/--id/--cnt/--dt-from/--dt-until/--created-from/--created-until) один в один,
# разница только в конечном действии: archive перемещает, delete стирает безвозвратно.
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

echo "--- ds get: все три клиента активны в основной таблице ---"
$DS --db "$DB" get --dt 1704067200 --src CRM

echo "--- ds archive --where is_test_account=true --yes ---"
$DS --db "$DB" archive --src CRM --where is_test_account=true --yes

echo "--- ds get: клиент 102 (test-аккаунт) пропал из основной таблицы целиком ---"
$DS --db "$DB" get --dt 1704067200 --src CRM

echo "--- ds get --archive: 102 виден при явном запросе архива, вместе с email ---"
$DS --db "$DB" get --dt 1704067200 --src CRM --archive
