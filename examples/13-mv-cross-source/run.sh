#!/usr/bin/env bash
# `ds mv --src SRC --lb LB --to-src SRC2 --to-lb LB2`: показатель "manufacturer"
# раньше заходил из CRM, а теперь поставляется из ERP (оба источника уже существуют и
# имеют собственные данные). `ds mv` переносит ВСЮ историю показателя (активную и
# архивную) в указанный источник -- физически переписывает lb/src на каждой
# затронутой транзакции, не создавая новых записей журнала.
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

$DS --db "$DB" load "$HERE/sources/CRM" "$HERE/batch_crm.json" --dt 1704067200
$DS --db "$DB" load "$HERE/sources/ERP" "$HERE/batch_erp.json" --dt 1704067200

echo "--- ds get --src CRM: manufacturer пока в CRM ---"
$DS --db "$DB" get --dt 1704067200 --src CRM

echo "--- ds mv --src CRM --lb manufacturer --to-src ERP --to-lb manufacturer --yes ---"
$DS --db "$DB" mv --src CRM --lb manufacturer --to-src ERP --to-lb manufacturer --yes

echo "--- ds get --src CRM: manufacturer больше не существует в CRM ---"
$DS --db "$DB" get --dt 1704067200 --src CRM

echo "--- ds get --src ERP: manufacturer теперь здесь, рядом с уже бывшими данными ---"
$DS --db "$DB" get --dt 1704067200 --src ERP
