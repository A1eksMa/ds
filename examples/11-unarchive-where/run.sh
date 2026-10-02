#!/usr/bin/env bash
# `ds unarchive --where LB=VALUE`: зеркало `ds archive --where` -- тот же селектор
# (резолвится через ту же свёртку Level 1, активные + архивные), но переносит подходящие
# АРХИВНЫЕ транзакции обратно в активную таблицу. `--where` работает одинаково в обе
# стороны, потому что условие проверяется по текущему (свёрнутому) значению, а не по тому,
# в какой физически таблице лежит запись сейчас.
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

echo "--- ds archive --where is_test_account=true --yes ---"
$DS --db "$DB" archive --src CRM --where is_test_account=true --yes

echo "--- ds get: клиент 102 (test-аккаунт) в архиве, не виден без --archive ---"
$DS --db "$DB" get --dt 1704067200 --src CRM

echo "--- ds unarchive --where is_test_account=true --yes ---"
$DS --db "$DB" unarchive --src CRM --where is_test_account=true --yes

echo "--- ds get: клиент 102 снова активен, как до архивирования ---"
$DS --db "$DB" get --dt 1704067200 --src CRM
