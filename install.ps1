# VKAssistant - Скрипт установки для Windows
# Запустите в PowerShell: .\install.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VKAssistant - Установка для Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка Python
Write-Host "[1/5] Проверка Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Найден: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Python не найден!" -ForegroundColor Red
    Write-Host "  Установите Python 3.8+ с https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

# Создание виртуального окружения
Write-Host ""
Write-Host "[2/5] Создание виртуального окружения..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "  Виртуальное окружение уже существует" -ForegroundColor Green
} else {
    python -m venv venv
    Write-Host "  ✅ Виртуальное окружение создано" -ForegroundColor Green
}

# Установка зависимостей
Write-Host ""
Write-Host "[3/5] Установка зависимостей..." -ForegroundColor Yellow
.\venv\Scripts\pip.exe install -r requirements.txt
Write-Host "  ✅ Зависимости установлены" -ForegroundColor Green

# Создание .env файла
Write-Host ""
Write-Host "[4/5] Настройка .env файла..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  Файл .env уже существует" -ForegroundColor Green
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✅ Создан файл .env" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ⚠️  ВАЖНО: Заполните .env файл перед запуском!" -ForegroundColor Yellow
    Write-Host "  - VK_GROUP_ID: ID вашего сообщества (отрицательное число)" -ForegroundColor Yellow
    Write-Host "  - VK_TOKEN: токен доступа сообщества" -ForegroundColor Yellow
    Write-Host "  - WEATHER_API_KEY: API ключ OpenWeatherMap (опционально)" -ForegroundColor Yellow
    Write-Host "  - ADMIN_ID: ваш VK ID" -ForegroundColor Yellow
}

# Инициализация git
Write-Host ""
Write-Host "[5/5] Инициализация Git..." -ForegroundColor Yellow
if (Test-Path ".git") {
    Write-Host "  Git уже инициализирован" -ForegroundColor Green
} else {
    git init
    git add .
    git commit -m "Initial commit: VKAssistant setup"
    Write-Host "  ✅ Git инициализирован" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ Установка завершена!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Следующие шаги:" -ForegroundColor Yellow
Write-Host "1. Заполните файл .env (токены и ID)" -ForegroundColor White
Write-Host "2. Запустите бота: .\venv\Scripts\python.exe main.py" -ForegroundColor White
Write-Host ""
Write-Host "📖 Подробная инструкция в README.md" -ForegroundColor Cyan
Write-Host ""
