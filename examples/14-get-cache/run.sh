#!/usr/bin/env bash
# ds get --cache: инкрементальная свёртка (см. docs/decisions/0010-incremental-fold-cache.md).
# Второй `ds get --cache` после нового `load` досчитывает только новые транзакции вместо
# полной пересборки, но даёт побайтово тот же результат, что обычный `ds get` без кэша --
# последние два блока вывода ниже идентичны.
# Использование:  bash run.sh [WORKDIR]   (env DS — переопределение команды)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${1:-$(mktemp -d)}"
DB="$WORK/data.db"
CACHE="$WORK/get-cache.json"
DS="${DS:-python3 -m src.cli.commands}"

cd "$REPO"
export PYTHONPATH="$REPO"
echo "workdir: $WORK" >&2

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch1.json" --dt 1704067200

echo "--- ds get --dt 1704067200 --cache get-cache.json (первый вызов: кэша ещё нет -- полная пересборка, кэш создаётся) ---"
$DS --db "$DB" get --dt 1704067200 --cache "$CACHE"

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch2.json" --dt 1706745600

echo "--- ds get --dt 1706745600 --cache get-cache.json (второй вызов: источник не менялся структурно -- досчитываются только новые транзакции) ---"
$DS --db "$DB" get --dt 1706745600 --cache "$CACHE"

echo "--- ds get --dt 1706745600 (без --cache, для сравнения -- результат тот же) ---"
$DS --db "$DB" get --dt 1706745600
