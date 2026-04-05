#!/bin/bash
# VKAssistant - Скрипт установки для Linux
# Загружает deploy.sh во временную папку и запускает

echo "========================================"
echo "  VKAssistant - Загрузка установщика"
echo "========================================"
echo ""

# Загружаем deploy.sh во временную папку
TEMP_DIR=$(mktemp -d)
DEPLOY_SCRIPT="$TEMP_DIR/deploy.sh"

echo "📥 Загрузка установщика..."
curl -sSL "https://raw.githubusercontent.com/Drentis/VKAssistant/main/deploy.sh" -o "$DEPLOY_SCRIPT"

if [ ! -f "$DEPLOY_SCRIPT" ]; then
    echo "❌ Не удалось загрузить установщик"
    echo "Проверьте подключение к интернету"
    exit 1
fi

chmod +x "$DEPLOY_SCRIPT"

echo "✅ Установщик загружен"
echo ""
echo "🚀 Запуск установки..."
echo ""

# Запускаем deploy.sh от root
sudo bash "$DEPLOY_SCRIPT"

# Очищаем
rm -rf "$TEMP_DIR"
