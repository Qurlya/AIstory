#!/bin/bash

cd $(dirname $0)/..
source .env

BACKUP_DIR="./database/backups"
mkdir -p $BACKUP_DIR

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/manual_$DATE.sql.gz"

echo "📦 Создание ручного бэкапа..."

docker exec aistory-database-1 mariadb-dump \
  -u${DB_USER} \
  -p${DB_PASS} \
  ${DB_NAME} | gzip > $BACKUP_FILE

if [ $? -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Бэкап создан: $BACKUP_FILE ($SIZE)"

else
    echo "❌ Ошибка создания бэкапа!"
    rm -f $BACKUP_FILE
    exit 1
fi