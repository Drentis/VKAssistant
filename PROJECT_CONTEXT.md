# VKAssistant - Контекст проекта
# Последнее обновление: 2026-04-11

## 📍 Текущее состояние

✅ **VKAssistant полностью работает!**

### Что сделано:
- ✅ VK бот работает с Long Poll
- ✅ Все функции работают (покупки, дела, учёба, идеи, рецепты, погода)
- ✅ Inline клавиатуры исправлены (компактный формат)
- ✅ Настройки работают (видимость кнопок, триггеры, погода)
- ✅ Привязка аккаунтов TG ↔ VK готова (таблица account_links в БД)
- ✅ Система установки на сервер (deploy.sh, install.sh, vkactl)
- ✅ Установка для Windows (install.ps1)
- ✅ Документация (README.md, QUICKSTART.md)
- ✅ Планировщик напоминаний о делах
- ✅ Планировщик погоды с уведомлениями о дожде

### Что НЕ сделано:
- ❌ Telegram бот не интегрирован (проблемы с подключением к api.telegram.org)
- ❌ UnifiedAssistant удалён (отложили)
- ❌ Привязка аккаунтов не тестировалась (нужен работающий TG)

---

## 📁 Структура проекта

```
VKAssistant/
├── main.py              # Основной файл (VK бот, ~2500 строк)
├── database.py          # БД SQLite + привязка аккаунтов
├── config.py            # Конфигурация (VK_GROUP_ID, VK_TOKEN, WEATHER_API_KEY, ADMIN_ID)
├── requirements.txt     # vk-api, aiosqlite, python-dotenv, aiohttp
├── .env                 # Токены (НЕ коммитить!)
├── .env.example         # Шаблон .env
├── .gitignore           # Исключения для Git
├── deploy.sh            # Развёртывание на Linux сервере
├── install.sh           # Загрузчик deploy.sh
├── install.ps1          # Установка для Windows
├── README.md            # Документация
├── QUICKSTART.md        # Быстрый старт
├── CHANGELOG.md         # История изменений
└── notebook.db          # База данных (создаётся автоматически)
```

---

## 🔧 Ключевые технические детали

### Зависимости:
- vk-api>=2.0.0 (VK API + Long Poll)
- aiosqlite>=0.19.0 (асинхронная БД)
- aiohttp>=3.8.0 (HTTP запросы для погоды)
- python-dotenv>=1.0.0 (загрузка .env)

### Версия Python: 3.14
- ⚠️ `asyncio.get_event_loop()` устарел → использовать `asyncio.run()` или `asyncio.new_event_loop()`
- ⚠️ `datetime.UTC` не работает → импортировать `from datetime import UTC`

### VK Long Poll:
- Group ID должен быть **положительным** (без минуса) для VkBotLongPoll
- В .env хранится с минусом: `VK_GROUP_ID=-237379918`
- В коде: `group_id = int(str(VK_GROUP_ID).lstrip('-'))`

### Inline клавиатуры VK:
- Максимум **10 строк** на клавиатуру
- Использовать `get_compact_inline_keyboard()` для объединения кнопок по 2 в строку
- Формат: плоский список `[{text, color, payload}, ...]`

### Callback payload:
- VK уже парсит JSON → `event.obj.payload` это **dict**, не строка
- В `handle_callback()`: проверять `isinstance(payload, str)` перед `json.loads()`

### База данных:
- Путь: `notebook.db` (в той же директории)
- Таблица `account_links` для привязки TG ↔ VK
- Функции: `generate_link_code()`, `link_accounts_by_code()`, `get_linked_vk_id()`, `get_linked_tg_id()`

### Погода:
- API: OpenWeatherMap (https://openweathermap.org/api)
- Функция: `get_weather(city)` в main.py
- Возвращает: `{success, temp, feels_like, description, icon, humidity, wind_speed, city, timezone}`

---

## 🚀 Как запустить

### Локально (Windows):
```powershell
cd c:\Users\Drentis\Documents\VKAssistant\VKAssistant
python main.py
```

### На сервере (Linux):
```bash
# Установка одной командой:
curl -sSL https://raw.githubusercontent.com/Drentis/VKAssistant/main/install.sh | sudo bash

# Управление:
vkactl status
vkactl logs
vkactl restart
vkactl update
vkactl edit
```

---

## 📝 Следующие шаги (если нужно продолжить)

### 1. Добавить Telegram (когда будет работать подключение)
- Раскомментировать `ENABLED_PLATFORMS=both` в .env
- Добавить TG токен
- Интегрировать aiogram из TelegramAssistant
- Тестировать привязку аккаунтов

### 2. Улучшить VK бота
- Добавить FSM для рецептов (сейчас заглушка)
- Добавить inline кнопки для редактирования списков
- Добавить админ-панель (статистика)
- Добавить планировщик напоминаний (сейчас не реализован)

### 3. Деплой на сервер
- Загрузить на GitHub
- Протестировать deploy.sh
- Настроить systemd сервис

---

## ⚠️ Известные проблемы

1. **Telegram не подключается** — `api.telegram.org` недоступен (возможно заблокирован)
   - Решение: использовать VPN/прокси или запускать на сервере

---

## 🔑 Токены (для справки)

- VK_GROUP_ID: `-237379918`
- VK_TOKEN: рабочий (в .env)
- WEATHER_API_KEY: `15751c8226d0252f81438313e2e35a92` (рабочий)
- ADMIN_ID: `295929531`

---

## 📚 Полезные ссылки

- VK API Docs: https://dev.vk.com/ru/api/bot
- Long Poll: https://dev.vk.com/ru/api/bot/long-poll
- vk-api Python: https://vk-api.readthedocs.io/
- OpenWeatherMap: https://openweathermap.org/api

---

## 💡 Советы для продолжения

1. **Всегда проверяйте синтаксис** перед запуском:
   ```bash
   python -m py_compile main.py
   ```

2. **Смотрите логи** при ошибках:
   ```bash
   journalctl -u vkassistant -f  # на сервере
   # или просто вывод консоли локально
   ```

3. **Тестируйте изменения** локально перед деплоем на сервер

4. **Делайте коммиты** после каждого рабочего изменения

---

**Проект готов к продолжению работы!** 🚀
