#!/usr/bin/env bash
# `ds update`: синхронизирует labels[] в source.json с тем, что реально есть в
# БД -- добавляет показатели с данными, которых в файле нет, убирает объявленные
# показатели, у которых не осталось ни одной транзакции. Копируем sources/ в
# WORKDIR, чтобы update писал в копию, а не в закоммиченную фикстуру примера.
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

cp -r "$HERE/sources" "$WORK/sources"
SRC_DIR="$WORK/sources/CRM"

echo "--- source.json до update ---"
cat "$SRC_DIR/source.json"

$DS --db "$DB" load "$SRC_DIR" "$HERE/batch.json" --dt 1704067200

echo "--- ds update: old_junk_field никогда не грузился, email/phone пришли явочным порядком ---"
$DS --db "$DB" update "$SRC_DIR"

echo "--- source.json после update ---"
cat "$SRC_DIR/source.json"
