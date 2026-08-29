#!/usr/bin/env bash
# Базовая загрузка: два батча в один источник CRM.
# Использование:  bash run.sh [WORKDIR]
#   WORKDIR — куда положить data.db (по умолчанию — временная папка).
#   DS      — переопределение команды (по умолчанию: python3 -m src.cli.commands).
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
