"""
Модуль конфигурации VKAssistant.

Загружает переменные окружения из файла .env:
- VK_GROUP_ID: ID сообщества ВКонтакте (отрицательное число)
- VK_TOKEN: токен доступа сообщества (получить в управлении сообществом)
- WEATHER_API_KEY: API ключ OpenWeatherMap (https://openweathermap.org/api)
- ADMIN_ID: VK ID администратора (положительное число)

Пример .env файла:
    VK_GROUP_ID=-123456789
    VK_TOKEN=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
    WEATHER_API_KEY=abcd1234efgh5678ijkl9012mnop3456
    ADMIN_ID=123456789
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# ID сообщества ВКонтакте (отрицательное число, например -123456789)
VK_GROUP_ID = os.getenv("VK_GROUP_ID")

# Токен доступа сообщества VK
# Получить можно в Управление сообществом -> Работа с API -> Создать ключ
VK_TOKEN = os.getenv("VK_TOKEN")

# API ключ для сервиса OpenWeatherMap (используется для прогноза погоды)
# Получить ключ можно на https://openweathermap.org/api
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# VK ID администратора бота (положительное число)
# Получить можно через vk.com/foaf.php?id=YOUR_ID
ADMIN_ID = os.getenv("ADMIN_ID")
