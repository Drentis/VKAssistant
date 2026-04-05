#!/bin/bash

# ============================================================
# Скрипт быстрого развёртывания VKAssistant с GitHub
# ============================================================
# Использование:
#   curl -sSL https://raw.githubusercontent.com/Drentis/VKAssistant/master/deploy.sh | sudo bash
# Или:
#   wget -qO- https://raw.githubusercontent.com/Drentis/VKAssistant/master/deploy.sh | sudo bash
# ============================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Логотип
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   VKAssistant - Быстрое развёртывание                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Пожалуйста, запустите от root (sudo ...)${NC}"
    exit 1
fi

# ============================================================
# КОНСТАНТЫ
# ============================================================
BOT_USER="vkassistant"
BOT_DIR="/opt/vkassistant"
DEFAULT_REPO="https://github.com/Drentis/VKAssistant.git"
REPO_URL="${1:-$DEFAULT_REPO}"
BRANCH="${2:-main}"

echo -e "\n${YELLOW}📦 Репозиторий: $REPO_URL${NC}"
echo -e "${YELLOW}📦 Ветка: $BRANCH${NC}"

# ============================================================
# ПОЛНОЕ УДАЛЕНИЕ СТАРОЙ ВЕРСИИ
# ============================================================
echo -e "\n${RED}⚠️  ПРОВЕРКА НАЛИЧИЯ СТАРОЙ ВЕРСИИ...${NC}"

if systemctl is-active --quiet vkassistant 2>/dev/null; then
    echo -e "${YELLOW}   Остановка старого сервиса...${NC}"
    systemctl stop vkassistant
    systemctl disable vkassistant
    echo -e "${GREEN}   ✓ Сервис остановлен${NC}"
fi

if [ -f /etc/systemd/system/vkassistant.service ]; then
    echo -e "${YELLOW}   Удаление старого systemd сервиса...${NC}"
    rm -f /etc/systemd/system/vkassistant.service
    systemctl daemon-reload
    echo -e "${GREEN}   ✓ Сервис удалён${NC}"
fi

if [ -d "$BOT_DIR" ]; then
    echo -e "${YELLOW}   Удаление старой директории $BOT_DIR...${NC}"
    rm -rf "$BOT_DIR"
    echo -e "${GREEN}   ✓ Директория удалена${NC}"
fi

if id "$BOT_USER" &>/dev/null; then
    echo -e "${YELLOW}   Удаление старого пользователя $BOT_USER...${NC}"
    userdel -r "$BOT_USER" 2>/dev/null || userdel "$BOT_USER" 2>/dev/null || true
    echo -e "${GREEN}   ✓ Пользователь удалён${NC}"
fi

if [ -f /usr/local/bin/vkactl ]; then
    echo -e "${YELLOW}   Удаление старого vkactl...${NC}"
    rm -f /usr/local/bin/vkactl
    echo -e "${GREEN}   ✓ vkactl удалён${NC}"
fi

echo -e "${GREEN}   ✓ Старая версия полностью удалена${NC}"

# ============================================================
# Обновление системы
# ============================================================
echo -e "\n${MAGENTA}[1/8] Обновление пакетов...${NC}"
apt update -qq && apt upgrade -y -qq

# ============================================================
# Установка зависимостей
# ============================================================
echo -e "\n${MAGENTA}[2/8] Установка зависимостей...${NC}"
apt install -y -qq python3 python3-pip python3-venv git curl

# ============================================================
# Создание пользователя и директории
# ============================================================
echo -e "\n${MAGENTA}[3/8] Создание пользователя и директории...${NC}"

if ! id "$BOT_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$BOT_DIR" "$BOT_USER"
    echo -e "${GREEN}   ✓ Пользователь $BOT_USER создан${NC}"
else
    echo -e "${GREEN}   ✓ Пользователь $BOT_USER уже существует${NC}"
fi

mkdir -p "$BOT_DIR"
chown "$BOT_USER:$BOT_USER" "$BOT_DIR"
echo -e "${GREEN}   ✓ Директория $BOT_DIR создана${NC}"

# ============================================================
# Клонирование репозитория
# ============================================================
echo -e "\n${MAGENTA}[4/8] Загрузка файлов бота...${NC}"

git config --global --add safe.directory "$BOT_DIR" 2>/dev/null || true

cd "$BOT_DIR"

echo -e "${YELLOW}   Клонирование репозитория...${NC}"
su -s /bin/bash "$BOT_USER" -c "git clone $REPO_URL . 2>/dev/null" || {
    echo -e "${RED}   ❌ Не удалось клонировать репозиторий${NC}"
    exit 1
}
su -s /bin/bash "$BOT_USER" -c "git checkout main 2>/dev/null" || true
echo -e "${GREEN}   ✓ Репозиторий клонирован${NC}"

if [ ! -f "$BOT_DIR/requirements.txt" ]; then
    echo -e "${RED}   ❌ requirements.txt не найден!${NC}"
    rm -rf "$BOT_DIR"/*
    su -s /bin/bash "$BOT_USER" -c "git clone $REPO_URL . 2>/dev/null" || exit 1
    echo -e "${GREEN}   ✓ Репозиторий перезагружен${NC}"
fi

# ============================================================
# Настройка виртуального окружения
# ============================================================
echo -e "\n${MAGENTA}[5/8] Настройка виртуального окружения...${NC}"
su -s /bin/bash "$BOT_USER" -c "python3 -m venv venv"
echo -e "${GREEN}   ✓ Виртуальное окружение создано${NC}"

echo -e "\n${YELLOW}   Установка зависимостей Python...${NC}"
su -s /bin/bash "$BOT_USER" -c "$BOT_DIR/venv/bin/pip install --upgrade pip -q"
su -s /bin/bash "$BOT_USER" -c "$BOT_DIR/venv/bin/pip install -r $BOT_DIR/requirements.txt -q"
echo -e "${GREEN}   ✓ Зависимости установлены${NC}"

# ============================================================
# Настройка .env файла с интерактивным вводом
# ============================================================
echo -e "\n${MAGENTA}[6/8] Настройка токенов${NC}"

# Заголовок для VK
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           НАСТРОЙКА VK COMMUNITY TOKEN                   ║${NC}"
echo -e "${BLUE}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║  1. Перейдите в ваше сообщество VK                       ║${NC}"
echo -e "${BLUE}║  2. Управление → Работа с API                            ║${NC}"
echo -e "${BLUE}║  3. Создайте ключ с правами messages и manage            ║${NC}"
echo -e "${BLUE}║  4. Скопируйте токен                                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Ввод VK GROUP ID
while true; do
    echo -en "${YELLOW}   Введите ID сообщества (например -123456789): ${NC}"
    read VK_GROUP_ID_INPUT < /dev/tty

    if [[ "$VK_GROUP_ID_INPUT" == -* ]] && [[ "$VK_GROUP_ID_INPUT" =~ ^-[0-9]+$ ]]; then
        echo -e "${GREEN}   ✓ ID сообщества принят${NC}"
        break
    else
        echo -e "${RED}   ❌ Неверный формат! ID должен начинаться с '-'${NC}"
    fi
done

# Ввод VK TOKEN
while true; do
    echo -en "${YELLOW}   Введите токен сообщества VK: ${NC}"
    read VK_TOKEN_INPUT < /dev/tty

    if [[ ${#VK_TOKEN_INPUT} -ge 20 ]]; then
        echo -e "${GREEN}   ✓ Токен принят${NC}"
        break
    else
        echo -e "${RED}   ❌ Слишком короткий токен!${NC}"
    fi
done

# Ввод API ключа погоды
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           НАСТРОЙКА OPENWEATHERMAP API KEY               ║${NC}"
echo -e "${BLUE}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║  API ключ для прогноза погоды (ОПЦИОНАЛЬНО)              ║${NC}"
echo -e "${BLUE}║  • Получить на https://openweathermap.org/api            ║${NC}"
echo -e "${BLUE}║  • Или нажмите Enter для пропуска                        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

while true; do
    echo -en "${YELLOW}   Введите API ключ погоды (или Enter для пропуска): ${NC}"
    read WEATHER_KEY_INPUT < /dev/tty

    if [[ -z "$WEATHER_KEY_INPUT" ]]; then
        echo -e "${YELLOW}   ⊘ Пропущено${NC}"
        break
    elif [[ ${#WEATHER_KEY_INPUT} -ge 16 ]]; then
        echo -e "${GREEN}   ✓ API ключ принят${NC}"
        break
    else
        echo -e "${RED}   ❌ Слишком короткий ключ!${NC}"
    fi
done

# Ввод ADMIN ID
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              НАСТРОЙКА ADMIN ID                          ║${NC}"
echo -e "${BLUE}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║  VK ID администратора (можно пропустить)                 ║${NC}"
echo -e "${BLUE}║  Получить через vk.com/foaf.php?id=YOUR_ID               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

while true; do
    echo -en "${YELLOW}   Введите VK ID администратора (или Enter): ${NC}"
    read ADMIN_ID_INPUT < /dev/tty

    if [[ -z "$ADMIN_ID_INPUT" ]]; then
        echo -e "${YELLOW}   ⊘ Пропущено${NC}"
        break
    elif [[ "$ADMIN_ID_INPUT" =~ ^[0-9]+$ ]]; then
        echo -e "${GREEN}   ✓ Admin ID принят${NC}"
        break
    else
        echo -e "${RED}   ❌ ID должен быть числом!${NC}"
    fi
done

# Создание .env
echo -e "\n${YELLOW}   Создание файла .env...${NC}"

cat > "$BOT_DIR/.env" << EOF
# ID сообщества ВКонтакте (отрицательное число)
VK_GROUP_ID=$VK_GROUP_ID_INPUT

# Токен доступа сообщества VK
VK_TOKEN=$VK_TOKEN_INPUT

# OpenWeatherMap API ключ
WEATHER_API_KEY=$WEATHER_KEY_INPUT

# VK ID администратора
ADMIN_ID=$ADMIN_ID_INPUT
EOF

chown "$BOT_USER:$BOT_USER" "$BOT_DIR/.env"
chmod 600 "$BOT_DIR/.env"
echo -e "${GREEN}   ✓ Файл .env создан${NC}"

# ============================================================
# Создание systemd сервиса
# ============================================================
echo -e "\n${MAGENTA}[7/8] Настройка автозапуска...${NC}"

cat > /etc/systemd/system/vkassistant.service << EOF
[Unit]
Description=VKAssistant Bot Service
After=network.target

[Service]
Type=simple
User=$BOT_USER
Group=$BOT_USER
WorkingDirectory=$BOT_DIR
ExecStart=$BOT_DIR/venv/bin/python $BOT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vkassistant

MemoryLimit=512M
CPUQuota=50%
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}   ✓ systemd сервис создан${NC}"

# ============================================================
# Запуск
# ============================================================
echo -e "\n${MAGENTA}[8/8] Запуск бота...${NC}"
systemctl daemon-reload
systemctl enable vkassistant -q
systemctl start vkassistant

sleep 2

if systemctl is-active --quiet vkassistant; then
    echo -e "${GREEN}   ✓ Бот успешно запущен!${NC}"
else
    echo -e "${RED}   ⚠ Бот запущен, но есть предупреждения${NC}"
    echo -e "${YELLOW}   Проверьте логи: journalctl -u vkassistant -n 20${NC}"
fi

# ============================================================
# Скрипт управления vkactl
# ============================================================
cat > /usr/local/bin/vkactl << 'EOF'
#!/bin/bash
ENV_FILE="/opt/vkassistant/.env"
BOT_USER="vkassistant"
BOT_DIR="/opt/vkassistant"

case "$1" in
    start) systemctl start vkassistant ;;
    stop) systemctl stop vkassistant ;;
    restart) systemctl restart vkassistant ;;
    status) systemctl status vkassistant ;;
    logs) journalctl -u vkassistant -f ;;
    reinstall)
        echo "🔄 Полная переустановка vkactl..."
        curl -sSL "https://raw.githubusercontent.com/Drentis/VKAssistant/main/deploy.sh" -o /tmp/deploy_new.sh
        if [ -f /tmp/deploy_new.sh ]; then
            NEW_VKACTL=$(sed -n '/^cat > \/usr\/local\/bin\/vkactl/,/^EOF$/p' /tmp/deploy_new.sh)
            if [ -n "$NEW_VKACTL" ]; then
                echo "$NEW_VKACTL" | bash
                chmod +x /usr/local/bin/vkactl
                echo "✅ vkactl переустановлен"
            else
                echo "❌ Не удалось извлечь скрипт"
            fi
        else
            echo "❌ Не удалось загрузить скрипт"
        fi
        rm -f /tmp/deploy_new.sh
        ;;
    update)
        echo "🔄 Обновление бота..."
        systemctl stop vkassistant 2>/dev/null || true
        git config --global --add safe.directory "$BOT_DIR" 2>/dev/null || true
        cd "$BOT_DIR"

        if [ ! -d ".git" ]; then
            echo "⚠️  .git не найден. Инициализация..."
            git init -q
            git remote add origin https://github.com/Drentis/VKAssistant.git
        fi

        echo "📥 Загрузка обновлений..."
        git fetch origin -q
        git checkout -f main -q
        git reset --hard origin/main -q

        echo "📦 Установка зависимостей..."
        "$BOT_DIR/venv/bin/pip" install -r "$BOT_DIR/requirements.txt" -q

        echo "🔧 Исправление прав..."
        chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"

        echo "🔄 Обновление vkactl..."
        curl -sSL "https://raw.githubusercontent.com/Drentis/VKAssistant/main/deploy.sh" -o /tmp/deploy_new.sh 2>/dev/null
        if [ -f /tmp/deploy_new.sh ]; then
            NEW_VKACTL=$(sed -n '/^cat > \/usr\/local\/bin\/vkactl/,/^EOF$/p' /tmp/deploy_new.sh)
            if [ -n "$NEW_VKACTL" ]; then
                echo "$NEW_VKACTL" | bash
                echo "✅ vkactl обновлён"
            fi
        fi
        rm -f /tmp/deploy_new.sh

        systemctl start vkassistant
        echo "✅ Обновлено!"
        ;;
    edit)
        echo "╔══════════════════════════════════════════════════════════╗"
        echo "║              РЕДАКТИРОВАНИЕ НАСТРОЕК                     ║"
        echo "╚══════════════════════════════════════════════════════════╝"
        echo ""
        echo "Что хотите отредактировать?"
        echo "  1) ID сообщества (VK_GROUP_ID)"
        echo "  2) Токен VK (VK_TOKEN)"
        echo "  3) API ключ погоды (WEATHER_API_KEY)"
        echo "  4) Admin ID (ADMIN_ID)"
        echo "  5) Редактировать .env вручную"
        echo "  0) Выход"
        echo ""
        read -p "Введите номер (0-5): " choice

        case $choice in
            1)
                read -p "Введите новый ID сообщества (например -123456789): " new_id
                if [[ "$new_id" == -* ]] && [[ "$new_id" =~ ^-[0-9]+$ ]]; then
                    sed -i "s/^VK_GROUP_ID=.*/VK_GROUP_ID=$new_id/" "$ENV_FILE"
                    echo "✓ ID сообщества обновлён"
                    systemctl restart vkassistant
                else
                    echo "❌ Неверный формат!"
                fi
                ;;
            2)
                read -p "Введите новый токен VK: " new_token
                if [[ ${#new_token} -ge 20 ]]; then
                    sed -i "s/^VK_TOKEN=.*/VK_TOKEN=$new_token/" "$ENV_FILE"
                    echo "✓ Токен обновлён"
                    systemctl restart vkassistant
                else
                    echo "❌ Слишком короткий токен!"
                fi
                ;;
            3)
                read -p "Введите новый API ключ погоды: " new_key
                sed -i "s/^WEATHER_API_KEY=.*/WEATHER_API_KEY=$new_key/" "$ENV_FILE"
                echo "✓ API ключ обновлён"
                systemctl restart vkassistant
                ;;
            4)
                read -p "Введите новый Admin ID: " new_admin
                if [[ "$new_admin" =~ ^[0-9]+$ ]]; then
                    sed -i "s/^ADMIN_ID=.*/ADMIN_ID=$new_admin/" "$ENV_FILE"
                    echo "✓ Admin ID обновлён"
                    systemctl restart vkassistant
                else
                    echo "❌ ID должен быть числом!"
                fi
                ;;
            5)
                nano "$ENV_FILE"
                echo "✓ .env отредактирован"
                systemctl restart vkassistant
                ;;
            0) echo "Выход" ;;
            *) echo "❌ Неверный номер" ;;
        esac
        ;;
    delete)
        echo "⚠️  УДАЛЕНИЕ БОТА"
        echo ""
        echo "Это действие удалит:"
        echo "  • Все данные пользователей"
        echo "  • Все настройки бота"
        echo "  • Системный сервис"
        echo "  • Файлы бота"
        echo "  • Пользователя vkassistant"
        echo "  • Команду vkactl"
        echo ""
        echo "⚠️  ВНИМАНИЕ: Это действие НЕОБРАТИМО!"
        echo ""
        read -p "Вы уверены? Введите 'yes' для подтверждения: " confirm
        if [ "$confirm" = "yes" ]; then
            echo ""
            echo "🔄 Остановка бота..."
            systemctl stop vkassistant 2>/dev/null || true
            systemctl disable vkassistant 2>/dev/null || true

            echo "🗑 Удаление сервиса..."
            rm -f /etc/systemd/system/vkassistant.service
            systemctl daemon-reload

            echo "🗑 Удаление логов..."
            journalctl --rotate 2>/dev/null || true

            echo "🗑 Удаление файлов бота..."
            rm -rf "$BOT_DIR"

            echo "🗑 Удаление пользователя..."
            userdel -r vkassistant 2>/dev/null || true

            echo "🗑 Удаление команды vkactl..."
            rm -f /usr/local/bin/vkactl

            echo ""
            echo "✅ Бот полностью удалён"
            echo ""
            echo "Для повторной установки:"
            echo "  curl -sSL https://raw.githubusercontent.com/Drentis/VKAssistant/main/deploy.sh | sudo bash"
        else
            echo "❌ Удаление отменено"
        fi
        ;;
    version)
        if [ -f "$BOT_DIR/main.py" ]; then
            VERSION=$(grep -oP 'BOT_VERSION = "\K[0-9.]+' "$BOT_DIR/main.py" 2>/dev/null || echo "unknown")
            echo "VKAssistant v$VERSION"
        else
            echo "VKAssistant v1.0.0"
        fi
        ;;
    *) echo "Использование: $0 {start|stop|restart|status|logs|update|reinstall|edit|delete|version}" ;;
esac
EOF

chmod +x /usr/local/bin/vkactl

# ============================================================
# Финальное сообщение
# ============================================================
echo -e "\n${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                  ✅ УСТАНОВКА ЗАВЕРШЕНА!                 ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  ✓ Бот установлен в /opt/vkassistant                     ║"
echo "║  ✓ Запущен как systemd сервис                            ║"
echo "║  ✓ Автозапуск при загрузке включён                       ║"
echo "║  ✓ Логирование настроено                                 ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Команды управления:                                     ║"
echo "║  • vkactl status    - Статус                             ║"
echo "║  • vkactl logs      - Логи в реальном времени            ║"
echo "║  • vkactl restart   - Перезапуск                         ║"
echo "║  • vkactl update    - Обновить из git                    ║"
echo "║  • vkactl edit      - Редактировать настройки            ║"
echo "║  • vkactl delete    - Удалить бота                       ║"
echo "║  • vkactl version   - Версия бота                        ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Проверка работы:                                        ║"
echo "║  1. Откройте ВКонтакте                                   ║"
echo "║  2. Перейдите в сообщения вашего сообщества              ║"
echo "║  3. Отправьте /start                                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

if grep -q "VK_GROUP_ID=-[0-9]" "$BOT_DIR/.env" 2>/dev/null; then
    echo -e "${GREEN}✓ ID сообщества настроен${NC}"
fi

if grep -q "VK_TOKEN=.\{20,\}" "$BOT_DIR/.env" 2>/dev/null; then
    echo -e "${GREEN}✓ Токен VK настроен${NC}"
fi

if grep -q "WEATHER_API_KEY=.\{16,\}" "$BOT_DIR/.env" 2>/dev/null; then
    echo -e "${GREEN}✓ API ключ погоды настроен${NC}"
else
    echo -e "${YELLOW}⊘ API ключ погоды не установлен${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Отправьте /start боту ВКонтакте!${NC}"
echo ""
