#!/bin/bash


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Загрузка .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ Файл .env не найден!"
    exit 1
fi

BACKUP_DIR="./database/backups"
mkdir -p $BACKUP_DIR

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/manual_$DATE.sql.gz"

echo "📦 Создание ручного бэкапа..."

# Ищем правильный контейнер
CONTAINER_NAME=$(docker ps --format "{{.Names}}" | grep -E "database|aistory.*database" | head -1)

if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ Контейнер с базой данных не найден!"
    exit 1
fi

echo "Использую контейнер: $CONTAINER_NAME"


docker exec $CONTAINER_NAME mariadb-dump \
  -u"${DB_USER}" \
  -p"${DB_PASS}" \
  "${DB_NAME}" | gzip > $BACKUP_FILE

if [ $? -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Бэкап создан: $BACKUP_FILE ($SIZE)"
else
    echo "❌ Ошибка создания бэкапа!"
    rm -f $BACKUP_FILE
    exit 1
fi