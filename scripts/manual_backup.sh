#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

BACKUP_DIR="./database/backups"
mkdir -p "$BACKUP_DIR"

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/manual_$DATE.sql.gz"

echo "📦 Создание ручного бэкапа..."

# Ищем контейнер
CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep -i 'database' | head -n 1)

if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ Контейнер с базой данных не найден!"
    exit 1
fi

echo "Использую контейнер: $CONTAINER_NAME"

# Выполняем дамп внутри контейнера, используя ЕГО СОБСТВЕННЫЕ переменные окружения
# Одинарные кавычки ' ' вокруг sh -c обязательны!
docker exec "$CONTAINER_NAME" sh -c 'mariadb-dump -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" "$MARIADB_DATABASE"' | gzip > "$BACKUP_FILE"

# Проверяем код возврата именно mariadb-dump
if [ ${PIPESTATUS[0]} -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Бэкап создан: $BACKUP_FILE ($SIZE)"
else
    echo "❌ Ошибка создания бэкапа!"
    rm -f "$BACKUP_FILE"
    exit 1
fi