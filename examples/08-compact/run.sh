#!/usr/bin/env bash
# `ds compact`: находит транзакции, повторяющие значение, уже действовавшее для
# того же (показатель, ключ) — X, X, Z -> вторая X ничего не меняет в срезе ни
# на один момент времени, значит она лишняя. По умолчанию -- в архив (мягко);
# --hard -- физическое удаление (как ds delete). Селектор -- --src (обязателен,
# как у delete/archive) + опционально --lb/--id/--dt-from/--dt-until.
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

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch1.json" --dt 1704067200   # status = active
$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch2.json" --dt 1704153600   # status = active (повтор)
$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch3.json" --dt 1704240000   # status = inactive (реальное изменение)

echo "--- ds compact --src CRM --yes ---"
$DS --db "$DB" compact --src CRM --yes

echo "--- ds get --archive: 3 транзакции на месте, просто одна теперь в архиве ---"
$DS --db "$DB" get --dt 1704240000 --src CRM --archive
