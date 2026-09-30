#!/usr/bin/env bash
# `ds upload`: как `ds load`, но отказывает целиком (ни одной строки), если в
# файле нашёлся показатель, которого нет ни в БД, ни в labels[] source.json,
# или значение не парсится под объявленный там тип. Оба отклонённых батча
# ниже завершаются кодом 1 -- намеренно гасим его через `|| true`, чтобы
# скрипт-пример досмотрел все три сценария до конца.
# Использование:  bash run.sh [WORKDIR]   (env DS — переопределение команды)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${1:-$(mktemp -d)}"
DB="$WORK/data.db"
DS="${DS:-python3 -m src.cli.commands}"
SRC="$HERE/sources/CRM"

cd "$REPO"
export PYTHONPATH="$REPO"
echo "workdir: $WORK" >&2

echo "--- ds upload: email/revenue объявлены заранее, типы совпадают -> проходит ---"
$DS --db "$DB" upload "$SRC" "$HERE/good.json" --dt 1704067200

echo "--- ds upload: utm_source не объявлен и раньше не грузился -> отказ целиком ---"
$DS --db "$DB" upload "$SRC" "$HERE/unknown_label.json" --dt 1704067200 2>&1 || true

echo "--- ds upload: revenue = 'fifty dollars' не парсится как number -> отказ целиком ---"
$DS --db "$DB" upload "$SRC" "$HERE/bad_type.json" --dt 1704067200 2>&1 || true

echo "--- ds get: только первая (успешная) загрузка реально попала в БД ---"
$DS --db "$DB" get --dt 1704067200 --src CRM
