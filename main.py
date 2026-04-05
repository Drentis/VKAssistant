"""
VKAssistant - Бот для ведения списков и заметок ВКонтакте.

Этот бот помогает управлять:
- Списком покупок с автоматической классификацией по магазинам
- Списком дел с напоминаниями и датами
- Учебными задачами
- Идеями и заметками
- Рецептами с ингредиентами
- Прогнозом погоды

Основные возможности:
- Автоматическая классификация товаров (Магнит/Фикспрайс/Другое)
- Напоминания о делах (ежедневно в 9:00)
- Прогноз погоды и уведомления о дожде
- Гибкие настройки (триггерные слова, видимость кнопок, названия магазинов)

Версия: 1.0.0
"""

# Версия бота
BOT_VERSION = "1.0.0"

import asyncio
import subprocess
import re
import aiohttp
import time
import json
from datetime import datetime, date, timedelta, UTC
from typing import Optional
import aiosqlite
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from vk_api.exceptions import ApiError

from config import VK_GROUP_ID, VK_TOKEN, WEATHER_API_KEY, ADMIN_ID
import database as db


# ============================================================
# === ПРОВЕРКА ПРАВ (Admin Check)
# ============================================================

def is_admin(user_id: int) -> bool:
    """
    Проверить, является ли пользователь администратором.

    Args:
        user_id: VK ID пользователя

    Returns:
        bool: True если пользователь администратор
    """
    if not ADMIN_ID:
        return False
    return str(user_id) == str(ADMIN_ID)


# ============================================================
# === КЛАВИАТУРЫ (Keyboards)
# ============================================================

def get_main_keyboard(settings: dict = None):
    """
    Создать главное меню с кнопками с учётом настроек видимости.

    Args:
        settings: Настройки пользователя (если None, все кнопки показываются)

    Returns:
        VkKeyboard: Клавиатура для главного меню
    """
    keyboard = VkKeyboard(one_time=False)

    # Собираем все кнопки
    buttons = []
    
    if settings is None or settings.get('visibility_shopping', 1):
        buttons.append(('🛒 Список покупок', VkKeyboardColor.POSITIVE))
    
    if settings is None or settings.get('visibility_todo', 1):
        buttons.append(('📋 Список дел', VkKeyboardColor.POSITIVE))
    
    if settings is None or settings.get('visibility_study', 1):
        buttons.append(('📚 Учёба', VkKeyboardColor.POSITIVE))
    
    if settings is None or settings.get('visibility_ideas', 1):
        buttons.append(('💡 Идеи', VkKeyboardColor.POSITIVE))
    
    if settings is None or settings.get('visibility_recipes', 1):
        buttons.append(('🍳 Рецепты', VkKeyboardColor.POSITIVE))
    
    if settings is None or settings.get('visibility_info', 1):
        buttons.append(('ℹ️ Инфо', VkKeyboardColor.SECONDARY))
    
    if settings is None or settings.get('weather_button', 1):
        buttons.append(('🌤 Погода', VkKeyboardColor.SECONDARY))
    
    # Добавляем кнопки по 2 в строку
    for i in range(0, len(buttons), 2):
        keyboard.add_button(buttons[i][0], color=buttons[i][1])
        if i + 1 < len(buttons):
            keyboard.add_button(buttons[i+1][0], color=buttons[i+1][1])
        keyboard.add_line()
    
    # Кнопка настроек на отдельной строке
    keyboard.add_button('⚙️ Настройки', color=VkKeyboardColor.NEGATIVE)

    return keyboard


def get_inline_keyboard(buttons: list):
    """
    Создать inline клавиатуру для VK.
    Автоматически объединяет кнопки по 2 в строку для экономии места.

    Args:
        buttons: Список кнопок в формате [[{text, color, payload}], ...]

    Returns:
        dict: JSON-структура для inline клавиатуры VK
    """
    keyboard = {"buttons": [], "one_time": False, "inline": True}

    # Если кнопки уже сгруппированы в строки, используем как есть
    # Но ограничиваем до 10 строк
    for row in buttons[:10]:
        button_row = []
        for btn in row:
            button_row.append({
                "action": {
                    "type": "callback",
                    "label": btn.get("text", "Button"),
                    "payload": json.dumps(btn.get("payload", {})),
                },
                "color": btn.get("color", "default")
            })
        keyboard["buttons"].append(button_row)

    return keyboard


def get_compact_inline_keyboard(buttons: list, max_rows=10):
    """
    Создать компактную inline клавиатуру, объединяя кнопки по 2 в строку.
    
    Args:
        buttons: Плоский список кнопок [{text, color, payload}, ...]
        max_rows: Максимальное количество строк (по умолчанию 10)
    
    Returns:
        dict: JSON-структура для inline клавиатуры VK
    """
    keyboard = {"buttons": [], "one_time": False, "inline": True}
    
    # Объединяем по 2 кнопки в строку
    for i in range(0, min(len(buttons), max_rows * 2), 2):
        row = []
        row.append({
            "action": {
                "type": "callback",
                "label": buttons[i].get("text", "Button"),
                "payload": json.dumps(buttons[i].get("payload", {})),
            },
            "color": buttons[i].get("color", "default")
        })
        if i + 1 < len(buttons):
            row.append({
                "action": {
                    "type": "callback",
                    "label": buttons[i+1].get("text", "Button"),
                    "payload": json.dumps(buttons[i+1].get("payload", {})),
                },
                "color": buttons[i+1].get("color", "default")
            })
        keyboard["buttons"].append(row)
    
    return keyboard


def get_shopping_categories_keyboard(settings: dict):
    """
    Создать inline клавиатуру с категориями списка покупок.

    Args:
        settings: Настройки пользователя

    Returns:
        dict: JSON-структура для inline клавиатуры
    """
    buttons = [
        [{
            "text": f"🥕 {settings['magnit_name']} ({settings.get('magnit_desc', 'Продукты')})",
            "color": "positive",
            "payload": {"type": "shopping", "category": "magnit"}
        }],
        [{
            "text": f"🏠 {settings['fixprice_name']} ({settings.get('fixprice_desc', 'Бытовое')})",
            "color": "positive",
            "payload": {"type": "shopping", "category": "fixprice"}
        }],
        [{
            "text": f"📦 {settings['other_name']} ({settings.get('other_desc', 'Другое')})",
            "color": "positive",
            "payload": {"type": "shopping", "category": "other"}
        }],
        [{
            "text": "🔙 Назад в меню",
            "color": "secondary",
            "payload": {"type": "back_to_main"}
        }]
    ]
    return get_inline_keyboard(buttons)


def get_items_keyboard(list_type: str, category: str = None, settings: dict = None):
    """
    Создать inline клавиатуру для просмотра списка элементов.

    Args:
        list_type: Тип списка (shopping, todo, study, ideas)
        category: Категория для shopping (magnit, fixprice, other)
        settings: Настройки пользователя

    Returns:
        dict: JSON-структура для inline клавиатуры
    """
    buttons = [
        [{
            "text": "✏️ Редактировать список",
            "color": "primary",
            "payload": {"type": "edit_list", "list_type": list_type, "category": category}
        }]
    ]

    # Добавляем кнопку "Назад" в зависимости от типа списка
    if list_type == "shopping":
        buttons.append([{
            "text": "🔙 Назад к категориям",
            "color": "secondary",
            "payload": {"type": "back_to_shopping"}
        }])
    else:
        buttons.append([{
            "text": "🔙 Назад в меню",
            "color": "secondary",
            "payload": {"type": "back_to_main"}
        }])

    return get_inline_keyboard(buttons)


def get_edit_keyboard(items: list, list_type: str, category: str = None, settings: dict = None):
    """
    Создать inline клавиатуру для редактирования списка.

    Args:
        items: Список элементов
        list_type: Тип списка (shopping, todo, study, ideas)
        category: Категория для shopping (magnit, fixprice, other)
        settings: Настройки пользователя

    Returns:
        dict: JSON-структура для inline клавиатуры
    """
    buttons = []

    # Ограничиваем до 8 элементов (VK макс 10 строк, 2 для доп кнопок)
    max_items = 8
    for item in items[:max_items]:
        item_id = item['id']

        if list_type == "shopping":
            item_text = item['item']
            taken = item['taken']

            if taken:
                buttons.append([{
                    "text": f"❌ {item_text}",
                    "color": "negative",
                    "payload": {"type": "toggle_item", "list_type": list_type, "category": category, "item_id": item_id}
                }])
            else:
                buttons.append([{
                    "text": f"✅ {item_text}",
                    "color": "positive",
                    "payload": {"type": "toggle_item", "list_type": list_type, "category": category, "item_id": item_id}
                }])
        else:
            if list_type == "ideas":
                item_text = item['idea'] if 'idea' in item.keys() else 'Без названия'
            else:
                item_text = item['task'] if 'task' in item.keys() else 'Без названия'

            # Обрезаем текст до 25 символов (чтобы поместились 2 кнопки)
            if len(item_text) > 25:
                item_text = item_text[:22] + "..."

            # Добавляем две кнопки: редактировать и удалить
            buttons.append([
                {
                    "text": f"✏️ {item_text}",
                    "color": "primary",
                    "payload": {"type": "edit_item", "list_type": list_type, "category": category, "item_id": item_id}
                },
                {
                    "text": "🗑 Удалить",
                    "color": "negative",
                    "payload": {"type": "delete_item", "list_type": list_type, "category": category, "item_id": item_id}
                }
            ])
    
    if len(items) > max_items:
        buttons.append([{
            "text": f"... и ещё {len(items) - max_items} (удалите через текст)",
            "color": "secondary",
            "payload": {"type": "noop"}
        }])

    buttons.append([{
        "text": "🗑 Очистить весь список",
        "color": "negative",
        "payload": {"type": "clear_list", "list_type": list_type, "category": category}
    }])

    # Кнопка "Назад" или "Готово"
    if list_type == "shopping":
        buttons.append([{
            "text": "✅ Готово",
            "color": "positive",
            "payload": {"type": "back_edit_list", "list_type": list_type, "category": category}
        }])
    else:
        buttons.append([{
            "text": "🔙 Назад в меню",
            "color": "secondary",
            "payload": {"type": "back_to_main"}
        }])

    return get_inline_keyboard(buttons)


# ============================================================
# === КЛАССИФИКАЦИЯ ТОВАРОВ (Product Classification)
# ============================================================

# Ключевые слова для классификации товаров по категориям
PRODUCT_KEYWORDS = [
    # Основные продукты
    "еда", "продукт", "молоко", "хлеб", "сыр", "колбаса", "мясо", "рыба",
    "овощ", "фрукт", "яблоко", "банан", "картофель", "морковь", "лук",
    "напиток", "вода", "сок", "чай", "кофе", "пиво", "вино",
    "сахар", "соль", "масло", "яйцо", "творог", "кефир", "йогурт",
    "печень", "торт", "конфет", "шоколад", "морожен", "булка", "батон",
    "круп", "рис", "греч", "макарон", "мука", "дрожж",
    "консерв", "тушён", "горошек", "кукуруз", "томат", "паст",
    "снек", "чипс", "сухар", "орех", "семеч",
    "детск", "пюре", "каш", "смес",
    "корм", "лакомств",
    
    # Дополнительные продукты
    "сырок", "сосиск", "сардел", "ветчин", "бекон",
    "пирож", "пирог", "печен", "пряник", "вафл",
    "хлебц", "лаваш", "лепешк",
    "сливк", "сметан", "майонез",
    "сельдер", "петруш", "укроп", "зелень",
    "чеснок", "перец", "имбирь", "лимон", "апельсин", "мандарин",
    "арбуз", "дыня", "виноград", "клубник", "малин", "смородин",
    "капуст", "свёкл", "реп", "редис", "огурц", "помидор",
    "гриб", "шампиньон", "вешенк",
    "икра", "креветк", "кальмар", "краб",
    "варень", "джем", "повидл", "мёд",
    "колбас", "сосиск", "сарделек",
    "пельмен", "вареник", "мант",
    "блин", "оладь",
    "сок", "нектар", "компот", "морс",
    "лимонад", "газировк", "квас",
    "энергетик", "тоник",
    "алкоголь", "водк", "коньяк", "виски",
    "сигарет", "сигар", "табак"
]

HOUSEHOLD_KEYWORDS = [
    # Бытовая химия и уборка
    "быт", "шампунь", "мыло", "гель", "порошок", "стир", "полоск",
    "убор", "тряп", "губк", "щётк", "веник", "швабр", "пылес",
    "туалет", "бумаг", "салфет", "полотенц", "платок",
    "посуд", "губк", "моющ", "средств", "чистящ",
    "космет", "крем", "лосьон", "маск", "скраб",
    "зуб", "паст", "щёток", "нит",
    "бритв", "лезв", "пен",
    "дезодор", "антиперспир",
    "парфюм", "дух", "туалетн",
    "лампоч", "батарей", "аккумулятор",
    "клей", "скотч", "изолент",
    "ножниц", "нож", "игл", "нитк",
    "канц", "руч", "карандаш", "тетрад", "блокнот", "папк",
    "игруш", "игра", "настол", "пазл",
    "декор", "свеч", "ваз", "рам",
    "посуд", "тарел", "чаш", "ложк", "вилк", "нож", "кастрюл", "сковород", "бокал", "кружк",
    
    # Дополнительные бытовые товары
    "подгузник", "памперс", "пеленк",
    "расческ", "гребеш", "заколк", "резинк",
    "мочалк", "пилк", "маникюр",
    "одеколон", "туалетн",
    "стирк", "отбеливат", "кондиционер",
    "освежит", "ароматиз",
    "мусор", "пакет", "мешок",
    "фольг", "пергамент", "рукав",
    "зажигал", "спичк",
    "фонар", "розетк", "удлинит",
    "провод", "зарядк", "блок питания",
    "гвозд", "шуруп", "саморез", "дюбель",
    "молот", "отвёртк", "плоскогубц", "ключ",
    "верёвк", "шнур", "провод",
    "замок", "замоч", "ключ",
    "ключниц", "вешалк", "плечик",
    "таз", "ведр", "совок",
    "коврик", "половик", "дорожк",
    "штор", "карниз", "тюль",
    "подушк", "одеял", "плед", "покрывал",
    "зеркал", "полк", "вешалк",
    "табурет", "стул", "столик"
]


def classify_item(item_text: str) -> str:
    """
    Классифицировать товар по категориям на основе ключевых слов.

    Args:
        item_text: Название товара

    Returns:
        str: Категория ("magnit", "fixprice", "other")
    """
    text_lower = item_text.lower()

    for keyword in PRODUCT_KEYWORDS:
        if keyword in text_lower:
            return "magnit"

    for keyword in HOUSEHOLD_KEYWORDS:
        if keyword in text_lower:
            return "fixprice"

    return "other"


def classify_item_with_custom(user_id: int, item_text: str) -> tuple[str, Optional[int]]:
    """
    Классифицировать товар с учётом пользовательских категорий.

    Args:
        user_id: ID пользователя
        item_text: Название товара

    Returns:
        tuple[str, Optional[int]]: (категория, category_id или None)
        Категория может быть "magnit", "fixprice", "other", или "custom_<id>"
    """
    text_lower = item_text.lower()

    # Сначала проверяем пользовательские категории
    custom_categories = run_async(db.get_custom_categories(user_id))

    for cat in custom_categories:
        if cat['keywords']:
            keywords = [kw.strip().lower() for kw in cat['keywords'].split(',')]
            for keyword in keywords:
                if keyword in text_lower:
                    return f"custom_{cat['id']}", cat['id']

    # Если не нашли в пользовательских, проверяем стандартные
    for keyword in PRODUCT_KEYWORDS:
        if keyword in text_lower:
            return "magnit", None

    for keyword in HOUSEHOLD_KEYWORDS:
        if keyword in text_lower:
            return "fixprice", None

    return "other", None


# ============================================================
# === ПАРСИНГ ДАТЫ (Date Parsing)
# ============================================================

def parse_date_from_text(text: str) -> tuple[str, Optional[date]]:
    """
    Извлечь дату из текста задачи.

    Args:
        text: Текст задачи

    Returns:
        tuple[str, Optional[date]]: (очищенный текст, дата или None)
    """
    today = date.today()
    due_date = None
    cleaned_text = text

    # Паттерны для даты
    patterns = [
        (r'\bзавтра\b', lambda: today + timedelta(days=1)),
        (r'\bпослезавтра\b', lambda: today + timedelta(days=2)),
        (r'\bсегодня\b', lambda: today),
    ]

    months = {
        'январ': 1, 'феврал': 2, 'март': 3, 'апрел': 4, 'май': 5, 'мая': 5,
        'июн': 6, 'июл': 7, 'август': 8, 'сентябр': 9, 'октябр': 10,
        'ноябр': 11, 'декабр': 12
    }

    # Проверка на "завтра", "послезавтра", "сегодня"
    for pattern, date_func in patterns:
        match = re.search(pattern, cleaned_text, re.IGNORECASE)
        if match:
            due_date = date_func()
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
            break

    # Проверка на дату в формате DD.MM
    if not due_date:
        match = re.search(r'(?:на\s*)?(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?', cleaned_text)
        if match:
            day, month, year = match.groups()
            day, month = int(day), int(month)
            year = int(year) if year else today.year
            if year < 100:
                year = 2000 + year
            try:
                due_date = date(year, month, day)
                cleaned_text = cleaned_text.replace(match.group(0), '').strip()
            except ValueError:
                pass

    # Проверка на дату в формате "DD месяца"
    if not due_date:
        match = re.search(r'(?:на\s*)?(\d{1,2})(?:-?го)?\s+(январ[яь]|феврал[яь]|март[аь]|апрел[яь]|мая|июн[яь]|июл[яь]|август[аь]|сентябр[яь]|октябр[яь]|ноябр[яь]|декабр[яь])', cleaned_text, re.IGNORECASE)
        if match:
            day, month_name = match.groups()
            day = int(day)
            month = months.get(month_name[:6])
            if month:
                try:
                    due_date = date(today.year, month, day)
                    if due_date < today:
                        due_date = date(today.year + 1, month, day)
                    cleaned_text = cleaned_text.replace(match.group(0), '').strip()
                except ValueError:
                    pass

    # Очистка от лишних пробелов
    cleaned_text = ' '.join(cleaned_text.split())

    return cleaned_text, due_date


# ============================================================
# === FSM СОСТОЯНИЯ (Finite State Machine)
# ============================================================

# Состояния пользователей
user_states = {}  # {user_id: {"state": "shopping", "data": {...}}}


def get_user_state(user_id: int) -> dict:
    """Получить состояние пользователя."""
    return user_states.get(user_id, {})


def set_user_state(user_id: int, state: str, data: dict = None):
    """Установить состояние пользователя."""
    user_states[user_id] = {"state": state, "data": data or {}}


def clear_user_state(user_id: int):
    """Очистить состояние пользователя."""
    if user_id in user_states:
        del user_states[user_id]


# ============================================================
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ VK
# ============================================================

# Глобальный event loop для run_async (создаётся один раз при запуске)
_async_loop = None

def get_async_loop():
    """Получить или создать глобальный event loop."""
    global _async_loop
    if _async_loop is None or _async_loop.is_closed():
        _async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_async_loop)
    return _async_loop

def run_async(coro):
    """
    Запустить асинхронную функцию из синхронного кода.
    Оптимизировано: использует один event loop вместо создания нового каждый раз.

    Args:
        coro: Асинхронная функция (coroutine)

    Returns:
        Результат выполнения coroutine
    """
    loop = get_async_loop()
    return loop.run_until_complete(coro)


def send_message(vk, user_id: int, message: str, keyboard=None):
    """
    Отправить сообщение пользователю.

    Args:
        vk: Объект VkApi method
        user_id: ID пользователя
        message: Текст сообщения
        keyboard: Клавиатура (VkKeyboard или dict для inline)
    """
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": get_random_id()
    }

    if keyboard:
        if isinstance(keyboard, VkKeyboard):
            params["keyboard"] = keyboard.get_keyboard()
        else:
            params["keyboard"] = json.dumps(keyboard)

    try:
        vk.messages.send(**params)
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")


def edit_message(vk, peer_id: int, conversation_message_id: int, message: str, keyboard=None):
    """
    Редактировать сообщение.

    Args:
        vk: Объект VkApi method
        peer_id: ID диалога
        conversation_message_id: ID сообщения
        message: Новый текст
        keyboard: Новая клавиатура
    """
    try:
        params = {
            "peer_id": peer_id,
            "conversation_message_id": conversation_message_id,
            "message": message,
        }
        if keyboard:
            params["keyboard"] = json.dumps(keyboard) if isinstance(keyboard, dict) else keyboard.get_keyboard()

        vk.messages.edit(**params)
    except Exception as e:
        print(f"Ошибка редактирования сообщения: {e}")


# ============================================================
# === ХЕНДЛЕРЫ (Handlers)
# ============================================================

def handle_start(vk, user_id: int):
    """Обработчик команды /start."""
    settings = run_async(db.get_category_settings(user_id))

    buy = settings.get('buy_trigger', 'купить')
    todo = settings.get('todo_trigger', 'сделать')
    study = settings.get('study_trigger', 'учёба')
    ideas = settings.get('ideas_trigger', 'идея')
    recipes = settings.get('recipes_trigger', 'рецепт')

    message = (
        f"👋 Привет! Я ваш личный помощник для заметок и списков.\n\n"
        f"🛒 Покупки — {buy} (товары сами распределяются по магазинам)\n"
        f"📋 Дела — {todo} (задачи с датами и напоминаниями)\n"
        f"📚 Учёба — {study} (учебные задачи)\n"
        f"💡 Идеи — {ideas} (быстрые заметки)\n"
        f"🍳 Рецепты — {recipes} (рецепты с ингредиентами)\n\n"
        f"⚙️ Настройки — настройте всё под себя\n"
        f"ℹ️ Инфо — подробная справка\n\n"
        f"💡 Лишние кнопки можно отключить в настройках\n\n"
        f"Выберите раздел:"
    )

    send_message(vk, user_id, message, keyboard=get_main_keyboard(settings))


def handle_help(vk, user_id: int):
    """Обработчик команды /help."""
    settings = run_async(db.get_category_settings(user_id))

    buy = settings.get('buy_trigger', 'купить')
    todo = settings.get('todo_trigger', 'сделать')
    study = settings.get('study_trigger', 'учёба')
    ideas = settings.get('ideas_trigger', 'идея')
    recipes = settings.get('recipes_trigger', 'рецепт')

    message = (
        f"ℹ️ ПОМОЩЬ\n\n"
        f"🛒 Покупки\n"
        f"• {buy} молоко, яйца — добавить товары\n"
        f"• {buy} хлеб — авто-классификация по магазинам\n"
        f"• м {buy} сыр — вручную в Магнит\n"
        f"• ф {buy} шампунь — вручную в Фикспрайс\n\n"
        f"📋 Дела\n"
        f"• {todo} уборку завтра — задача с датой\n"
        f"• {todo} проект 15.03 — задача на дату\n"
        f"• Напоминания приходят за день до срока\n\n"
        f"📚 Учёба\n"
        f"• {study} выучить 50 слов — учебная задача\n\n"
        f"💡 Идеи\n"
        f"• {ideas} записать мысль — быстрая заметка\n\n"
        f"🍳 Рецепты\n"
        f"• {recipes} Борщ — добавить рецепт\n"
        f"• Добавляйте ингредиенты по одному\n"
        f"• Кнопка «Добавить в корзину» перенесёт всё в покупки\n\n"
        f"🌤 Погода\n"
        f"• Настройте в ⚙️ Настройки → 🌤 Погода\n"
        f"• Ежедневные прогнозы и уведомления о дожде\n\n"
        f"⚙️ Настройки\n"
        f"• Меняйте названия магазинов\n"
        f"• Настраивайте триггерные слова\n"
        f"• Включайте/выключайте кнопки меню\n\n"
        f"Команды:\n"
        f"/start — Главное меню\n"
        f"/help — Эта справка\n"
        f"/cancel — Отменить текущее действие\n"
        f"/done — Завершить добавление рецепта\n"
        f"/version — Версия бота"
    )

    send_message(vk, user_id, message, keyboard=get_main_keyboard(settings))


def handle_version(vk, user_id: int):
    """Обработчик команды /version."""
    message = (
        f"🤖 VKAssistant\n\n"
        f"Версия: {BOT_VERSION}\n\n"
        f"Бот для ведения списков и заметок ВКонтакте"
    )
    send_message(vk, user_id, message)


def handle_admin(vk, user_id: int):
    """Обработчик команды /admin для администратора."""
    # Проверяем права админа
    if not is_admin(user_id):
        send_message(vk, user_id, "❌ Эта команда доступна только администратору.")
        return

    # Получаем общую статистику
    stats = run_async(db.get_global_stats())

    message = (
        f"📊 **АДМИН-ПАНЕЛЬ**\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"🛒 Товаров в покупках: {stats['total_shopping']}\n"
        f"📋 Задач в делах: {stats['total_todo']}\n"
        f"📚 Учебных задач: {stats['total_study']}\n"
        f"💡 Идей: {stats['total_ideas']}\n"
        f"🍳 Рецептов: {stats['total_recipes']}\n\n"
        f"Версия бота: {BOT_VERSION}\n\n"
        f"Выберите действие:"
    )

    # Создаём inline клавиатуру с админ-действиями
    buttons = [
        [
            {
                "text": "🔄 Обновить бота",
                "color": "positive",
                "payload": {"type": "admin_update_bot"}
            },
            {
                "text": "📋 Команды консоли",
                "color": "primary",
                "payload": {"type": "admin_console_commands"}
            }
        ],
        [
            {
                "text": "🗑 Очистить мою статистику",
                "color": "negative",
                "payload": {"type": "admin_clear_my_stats"}
            },
            {
                "text": "ℹ️ Моя статистика",
                "color": "primary",
                "payload": {"type": "admin_my_stats"}
            }
        ],
        [
            {
                "text": "🔙 Назад в меню",
                "color": "secondary",
                "payload": {"type": "back_to_main"}
            }
        ]
    ]

    keyboard = get_inline_keyboard(buttons)
    send_message(vk, user_id, message, keyboard=keyboard)


def handle_categories(vk, user_id: int):
    """Обработчик команды /categories для управления пользовательскими категориями."""
    categories = run_async(db.get_custom_categories(user_id))

    if not categories:
        message = (
            f"📂 **Пользовательские категории**\n\n"
            f"У вас пока нет пользовательских категорий.\n\n"
            f"Вы можете создавать свои магазины/категории с:\n"
            f"• Своим названием и иконкой\n"
            f"• Ключевыми словами для автоклассификации\n"
            f"• Сокращением для ручного выбора\n\n"
            f"Нажмите кнопку ниже, чтобы создать первую категорию:"
        )

        buttons = [[
            {
                "text": "➕ Создать категорию",
                "color": "positive",
                "payload": {"type": "custom_category_create"}
            }
        ]]
    else:
        message = f"📂 **Пользовательские категории**\n\n"
        message += f"У вас {len(categories)} категорий:\n\n"

        for cat in categories[:10]:  # Показываем максимум 10
            message += f"{cat['icon']} **{cat['name']}** (`{cat['short']}`)\n"
            if cat['description']:
                message += f"   _{cat['description']}_\n"
            if cat['keywords']:
                kw_count = len(cat['keywords'].split(','))
                message += f"   Ключевых слов: {kw_count}\n"
            message += "\n"

        if len(categories) > 10:
            message += f"... и ещё {len(categories) - 10}\n\n"

        buttons = [
            [
                {
                    "text": "➕ Создать категорию",
                    "color": "positive",
                    "payload": {"type": "custom_category_create"}
                },
                {
                    "text": "🔄 Обновить",
                    "color": "secondary",
                    "payload": {"type": "categories_refresh"}
                }
            ]
        ]

        # Добавляем кнопки для каждой категории (макс 6)
        for cat in categories[:6]:
            buttons.append([{
                "text": f"{cat['icon']} {cat['name']}",
                "color": "primary",
                "payload": {"type": "custom_category_view", "category_id": cat['id']}
            }])

    buttons.append([{
        "text": "🔙 Назад в меню",
        "color": "secondary",
        "payload": {"type": "back_to_main"}
    }])

    keyboard = get_inline_keyboard(buttons)
    send_message(vk, user_id, message, keyboard=keyboard)


def handle_update(vk, user_id: int):
    """Обработчик команды /update для обновления бота (админ)."""
    # Проверяем права админа
    if not is_admin(user_id):
        send_message(vk, user_id, "❌ Эта команда доступна только администратору.")
        return

    import subprocess
    import os
    import sys

    # Определяем директорию бота (где лежит main.py)
    bot_dir = os.path.dirname(os.path.abspath(__file__))

    # Определяем путь к pip в виртуальном окружении (кроссплатформенно)
    if sys.platform == 'win32':
        pip_path = os.path.join(bot_dir, 'venv', 'Scripts', 'pip.exe')
    else:
        pip_path = os.path.join(bot_dir, 'venv', 'bin', 'pip')

    send_message(vk, user_id, (
        f"🔄 **Проверка обновлений...**\n\n"
        f"Подождите, это может занять несколько минут."
    ))

    try:
        # Проверяем, есть ли .git директория
        git_dir = os.path.join(bot_dir, '.git')

        if not os.path.exists(git_dir):
            send_message(vk, user_id, (
                f"⚠️ **Git репозиторий не найден.**\n\n"
                f"Для обновления через Git необходимо:\n"
                f"1. Инициализировать git в директории бота\n"
                f"2. Добавить remote: https://github.com/Drentis/VKAssistant.git\n"
                f"3. Выполнить git pull\n\n"
                f"Или обновите вручную через `vkactl update` на сервере."
            ))
            return

        # Выполняем git pull
        result = subprocess.run(
            ['git', 'pull'],
            cwd=bot_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        result_stdout = result.stdout
        result_stderr = result.stderr

        # Проверяем результат
        if result_stderr and 'error' in result_stderr.lower():
            send_message(vk, user_id, f"❌ **Ошибка обновления:**\n{result_stderr[:500]}")
        else:
            # Устанавливаем зависимости
            if os.path.exists(os.path.join(bot_dir, 'requirements.txt')):
                subprocess.run(
                    [pip_path, 'install', '-r', os.path.join(bot_dir, 'requirements.txt')],
                    capture_output=True,
                    timeout=120
                )

            send_message(vk, user_id, (
                f"✅ **Бот обновлён!**\n\n"
                f"Обновления применены.\n\n"
                f"📝 **Что изменилось:**\n"
                f"{result_stdout[:500] if result_stdout else 'Файлы загружены'}\n\n"
                f"🔄 **Перезапуск через 3 секунды...**"
            ))

            # Автоматический перезапуск
            import time
            time.sleep(3)

            # Перезапуск процесса (кроссплатформенно)
            python_exe = sys.executable
            script_path = os.path.abspath(__file__)
            os.execv(python_exe, [python_exe, script_path])

    except subprocess.TimeoutExpired:
        send_message(vk, user_id, (
            f"❌ **Превышено время ожидания.**\n\n"
            f"Проверьте подключение к интернету и попробуйте ещё раз."
        ))
    except subprocess.CalledProcessError as e:
        send_message(vk, user_id, f"❌ **Ошибка выполнения команды:**\n{e.stderr[:500] if e.stderr else str(e)}")
    except Exception as e:
        send_message(vk, user_id, f"❌ **Произошла ошибка:**\n{str(e)}")


def handle_cancel(vk, user_id: int):
    """Обработчик команды /cancel."""
    clear_user_state(user_id)
    settings = run_async(db.get_category_settings(user_id))
    send_message(vk, user_id, "❌ Действие отменено.", keyboard=get_main_keyboard(settings))


def handle_done(vk, user_id: int):
    """Обработчик команды /done для завершения рецепта."""
    state = get_user_state(user_id)
    if state.get("state") != "adding_recipe":
        return

    data = state.get("data", {})
    recipe_name = data.get("recipe_name")
    ingredients = data.get("ingredients", [])

    if not recipe_name:
        clear_user_state(user_id)
        settings = run_async(db.get_category_settings(user_id))
        send_message(vk, user_id, "❌ Рецепт не найден.", keyboard=get_main_keyboard(settings))
        return

    # Переходим к состоянию добавления описания
    set_user_state(user_id, "adding_description", data)

    send_message(vk, user_id, (
        f"🍳 Рецепт: {recipe_name}\n"
        f"Ингредиенты: {len(ingredients)} шт.\n\n"
        f"Добавьте описание рецепта (необязательно):\n"
        f"Например: Перемешать всё и готовить при 180 градусах 15 минут\n\n"
        f"Чтобы пропустить, напишите пропустить.\n"
        f"Для отмены: /cancel"
    ))


def handle_shopping_button(vk, user_id: int):
    """Обработчик нажатия на кнопку 'Список покупок'."""
    settings = run_async(db.get_category_settings(user_id))

    keyboard = get_shopping_categories_keyboard(settings)

    message = (
        f"🛒 Список покупок\n\n"
        f"🥕 {settings['magnit_name']} — {settings.get('magnit_desc', 'Продукты')}\n"
        f"🏠 {settings['fixprice_name']} — {settings.get('fixprice_desc', 'Бытовое')}\n"
        f"📦 {settings['other_name']} — {settings.get('other_desc', 'Другое')}\n\n"
        f"Чтобы добавить товар, напишите:\n"
        f"{settings.get('buy_trigger', 'купить')} молоко\n\n"
        f"Можно использовать названия магазинов:\n"
        f"{settings['magnit_name']} {settings.get('buy_trigger', 'купить')} хлеб\n\n"
        f"Или сокращения:\n"
        f"{settings['magnit_short']} {settings.get('buy_trigger', 'купить')}...\n"
        f"{settings['fixprice_short']} {settings.get('buy_trigger', 'купить')}...\n"
        f"{settings['other_short']} {settings.get('buy_trigger', 'купить')}...\n\n"
        f"Выберите магазин для просмотра:"
    )

    send_message(vk, user_id, message, keyboard=keyboard)


def handle_todo_view(vk, user_id: int):
    """Просмотр списка дел."""
    settings = run_async(db.get_category_settings(user_id))
    items = run_async(db.get_todo_items(user_id))

    if not items:
        send_message(vk, user_id, "📋 Список дел пуст\n\nДобавьте первую задачу!", keyboard=get_main_keyboard(settings))
        return

    message = "📋 Список дел:\n\n"
    for item in items:
        emoji = "⚠️" if item['reminded'] else "📌"
        message += f"{emoji} {item['task']}"
        if item['due_date']:
            due = datetime.strptime(item['due_date'], '%Y-%m-%d').date()
            days_until = (due - date.today()).days
            if days_until == 0:
                message += " — сегодня"
            elif days_until == 1:
                message += " — завтра"
            elif days_until < 0:
                message += f" — просрочено ({abs(days_until)} дн. назад)"
            else:
                message += f" — через {days_until} дн. ({due.strftime('%d.%m.%Y')})"
        message += "\n"

    message += f"\nВсего: {len(items)}"
    keyboard = get_items_keyboard("todo", settings=settings)
    send_message(vk, user_id, message, keyboard=keyboard)


def handle_study_view(vk, user_id: int):
    """Просмотр списка учёбы."""
    settings = run_async(db.get_category_settings(user_id))
    items = run_async(db.get_study_items(user_id))

    if not items:
        send_message(vk, user_id, "📚 Список учёбы пуст\n\nДобавьте первую задачу!", keyboard=get_main_keyboard(settings))
        return

    message = "📚 Учёба:\n\n"
    for item in items:
        message += f"📖 {item['task']}\n"

    message += f"\nВсего: {len(items)}"
    keyboard = get_items_keyboard("study", settings=settings)
    send_message(vk, user_id, message, keyboard=keyboard)


def handle_ideas_view(vk, user_id: int):
    """Просмотр списка идей."""
    settings = run_async(db.get_category_settings(user_id))
    items = run_async(db.get_ideas(user_id))

    if not items:
        send_message(vk, user_id, "💡 Список идей пуст\n\nДобавьте первую идею!", keyboard=get_main_keyboard(settings))
        return

    message = "💡 Идеи:\n\n"
    for item in items:
        message += f"✨ {item['idea']}\n"

    message += f"\nВсего: {len(items)}"
    keyboard = get_items_keyboard("ideas", settings=settings)
    send_message(vk, user_id, message, keyboard=keyboard)


def handle_recipes_view(vk, user_id: int):
    """Просмотр списка рецептов."""
    settings = run_async(db.get_category_settings(user_id))
    items = run_async(db.get_recipes(user_id))

    if not items:
        send_message(vk, user_id, (
            "🍳 Список рецептов пуст\n\n"
            "Чтобы добавить рецепт, напишите:\n"
            "рецепт Название рецепта\n\n"
            "После этого бот предложит добавить ингредиенты.\n\n"
            "Для выхода напишите /cancel"
        ), keyboard=get_main_keyboard(settings))
        return

    # Создаём клавиатуру со списком рецептов
    buttons = []
    for item in items:
        buttons.append([{
            "text": f"📖 {item['name']}",
            "color": "primary",
            "payload": {"type": "recipe_view", "recipe_id": item['id']}
        }])

    buttons.append([{
        "text": "➕ Добавить рецепт",
        "color": "positive",
        "payload": {"type": "recipe_add_new"}
    }])
    buttons.append([{
        "text": "🔙 Назад в меню",
        "color": "secondary",
        "payload": {"type": "back_to_main"}
    }])

    keyboard = get_inline_keyboard(buttons)

    message = "🍳 Мои рецепты:\n\n"
    for item in items:
        ingredients = run_async(db.get_recipe_ingredients(item['id']))
        message += f"📖 {item['name']} — {len(ingredients)} инг.\n"

    message += f"\nВсего: {len(items)}"
    send_message(vk, user_id, message, keyboard=keyboard)


def handle_info_view(vk, user_id: int):
    """Просмотр информации о боте."""
    settings = run_async(db.get_category_settings(user_id))

    buy = settings.get('buy_trigger', 'купить')
    todo = settings.get('todo_trigger', 'сделать')
    study = settings.get('study_trigger', 'учёба')
    ideas = settings.get('ideas_trigger', 'идея')
    recipes = settings.get('recipes_trigger', 'рецепт')

    message = (
        f"ℹ️ СПРАВКА\n\n"
        f"Я помогу вам вести списки и заметки!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛒 СПИСОК ПОКУПОК\n"
        f"• Запишите: {buy} молоко, яйца\n"
        f"• Товары сами распределятся по магазинам\n"
        f"• Для ручной сортировки: м {buy} хлеб\n"
        f"• Отмечайте купленное и удаляйте лишнее\n\n"
        f"📋 СПИСОК ДЕЛ\n"
        f"• Запишите: {todo} уборку завтра\n"
        f"• Указывайте дату: завтра, 15.03, 10 марта\n"
        f"• Напоминание придёт за день до события\n\n"
        f"📚 УЧЁБА\n"
        f"• Запишите: {study} выучить 50 слов\n"
        f"• Все учебные задачи в одном месте\n\n"
        f"💡 ИДЕИ\n"
        f"• Запишите: {ideas} записать мысль\n"
        f"• Быстрые заметки для важных идей\n\n"
        f"🍳 РЕЦЕПТЫ\n"
        f"• Запишите: {recipes} Борщ\n"
        f"• Добавьте ингредиенты по одному\n"
        f"• Кнопка 'Добавить в корзину' перенесёт все продукты в список покупок\n\n"
        f"⚙️ НАСТРОЙКИ\n"
        f"• Меняйте названия магазинов\n"
        f"• Настраивайте команды\n"
        f"• Включайте и отключайте разделы\n\n"
        f"🌤 ПОГОДА\n"
        f"• Ежедневный прогноз в заданное время\n"
        f"• Предупреждения о дожде\n"
        f"• Настройте свой город\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Команды:\n"
        f"/start — Главное меню\n"
        f"/cancel — Отменить\n"
        f"/done — Завершить рецепт"
    )

    send_message(vk, user_id, message, keyboard=get_main_keyboard(settings))


def handle_settings_button(vk, user_id: int):
    """Нажатие на кнопку 'Настройки'."""
    set_user_state(user_id, "settings_choosing_category")
    settings = run_async(db.get_category_settings(user_id))

    is_admin_user = is_admin(user_id)

    # Создаём компактную клавиатуру (плоский список, объединится по 2 в строку)
    buttons = [
        {
            "text": f"🥕 {settings['magnit_name']}",
            "color": "primary",
            "payload": {"type": "settings_category", "category": "magnit"}
        },
        {
            "text": f"🏠 {settings['fixprice_name']}",
            "color": "primary",
            "payload": {"type": "settings_category", "category": "fixprice"}
        },
        {
            "text": f"📦 {settings['other_name']}",
            "color": "primary",
            "payload": {"type": "settings_category", "category": "other"}
        },
        {
            "text": "🔤 Триггеры",
            "color": "primary",
            "payload": {"type": "settings_triggers"}
        },
        {
            "text": "📱 Кнопки меню",
            "color": "primary",
            "payload": {"type": "settings_visibility"}
        },
        {
            "text": "🌤 Погода",
            "color": "primary",
            "payload": {"type": "settings_weather"}
        },
        {
            "text": "🗑 Сброс профиля",
            "color": "negative",
            "payload": {"type": "settings_reset_profile"}
        }
    ]

    if is_admin_user:
        buttons.append({
            "text": "👤 Админ-панель",
            "color": "negative",
            "payload": {"type": "admin_panel"}
        })
    
    buttons.append({
        "text": "🔙 Назад в меню",
        "color": "secondary",
        "payload": {"type": "back_to_main"}
    })

    keyboard = get_compact_inline_keyboard(buttons)

    admin_text = "\n\n👤 Админ-панель — статистика и обновление бота" if is_admin_user else ""

    message = (
        f"⚙️ Настройки\n\n"
        f"Выберите, что хотите настроить:\n\n"
        f"🥕 {settings['magnit_name']} — {settings.get('magnit_desc', 'Продукты')}\n"
        f"   Сокращение: {settings['magnit_short']}\n\n"
        f"🏠 {settings['fixprice_name']} — {settings.get('fixprice_desc', 'Бытовое')}\n"
        f"   Сокращение: {settings['fixprice_short']}\n\n"
        f"📦 {settings['other_name']} — {settings.get('other_desc', 'Другое')}\n"
        f"   Сокращение: {settings['other_short']}\n\n"
        f"🔤 Команды:\n"
        f"   Покупки: {settings.get('buy_trigger', 'купить')}\n"
        f"   Дела: {settings.get('todo_trigger', 'сделать')}\n"
        f"   Учёба: {settings.get('study_trigger', 'учёба')}\n"
        f"   Идеи: {settings.get('ideas_trigger', 'идея')}\n"
        f"   Рецепты: {settings.get('recipes_trigger', 'рецепт')}\n\n"
        f"🌤 Погода:\n"
        f"   Город: {settings.get('weather_city', 'не задан') or 'не задан'}\n"
        f"   Прогноз: {'✅' if settings.get('weather_daily', 0) else '❌'}\n"
        f"   Уведомление о дожде: {'✅' if settings.get('weather_rain', 1) else '❌'}\n\n"
        f"Нажмите на магазин, чтобы изменить название или сокращение.\n"
        f"Нажмите на 'Команды', чтобы изменить слова для добавления.\n"
        f"Нажмите на 'Погода', чтобы настроить прогнозы.{admin_text}\n\n"
        f"⚠️ Сброс профиля удалит все данные и настройки!"
    )

    send_message(vk, user_id, message, keyboard=keyboard)


# ============================================================
# === ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

def handle_text_message(vk, user_id: int, text: str):
    """Обработка текстовых сообщений."""
    text = text.strip()
    text_lower = text.lower()

    # Обрабатываем кнопки главного меню
    menu_buttons = {
        "🛒 список покупок": lambda: handle_shopping_button(vk, user_id),
        "📋 список дел": lambda: handle_todo_view(vk, user_id),
        "📚 учёба": lambda: handle_study_view(vk, user_id),
        "💡 идеи": lambda: handle_ideas_view(vk, user_id),
        "🍳 рецепты": lambda: handle_recipes_view(vk, user_id),
        "ℹ️ инфо": lambda: handle_info_view(vk, user_id),
        "⚙️ настройки": lambda: handle_settings_button(vk, user_id),
    }
    
    if text_lower in menu_buttons:
        menu_buttons[text_lower]()
        return
    
    # Кнопка погоды (требует settings)
    if text_lower == "🌤 погода":
        settings = run_async(db.get_category_settings(user_id))
        city = settings.get('weather_city', '')
        if not city:
            send_message(vk, user_id, (
                "❌ Город не задан\n\n"
                "Установите город в настройках:\n"
                "⚙️ Настройки → 🌤 Погода → 🏙 Город"
            ), keyboard=get_main_keyboard(settings))
        else:
            send_message(vk, user_id, "🌤 Запрашиваю погоду...", keyboard=get_main_keyboard(settings))
            weather = run_async(get_weather(city))
            if not weather.get("success"):
                send_message(vk, user_id, f"❌ {weather.get('error', 'Ошибка получения погоды')}", keyboard=get_main_keyboard(settings))
            else:
                icons = {"01d": "☀️", "01n": "🌙", "02d": "⛅", "02n": "☁️", "03d": "☁️", "03n": "☁️", "04d": "☁️", "04n": "☁️", "09d": "🌧", "09n": "🌧", "10d": "🌦", "10n": "🌧", "11d": "⛈", "11n": "⛈", "13d": "❄️", "13n": "❄️", "50d": "🌫", "50n": "🌫"}
                icon = icons.get(weather["icon"], "🌤")
                message = (
                    f"{icon} Погода сейчас\n\n"
                    f"📍 {weather['city']}\n"
                    f"🌡 +{weather['temp']}°C (ощущается как +{weather['feels_like']}°C)\n"
                    f"🌤 {weather['description'].capitalize()}\n"
                    f"💨 Ветер {weather['wind_speed']} м/с\n"
                    f"💧 Влажность {weather['humidity']}%\n\n"
                    f"Хорошего дня! ☀️"
                )
                send_message(vk, user_id, message, keyboard=get_main_keyboard(settings))
        return

    # Проверяем состояние пользователя
    state = get_user_state(user_id)

    # Обработка ввода в состоянии настроек
    if state.get("state") in ["settings_editing_name", "settings_editing_short", "settings_editing_desc"]:
        handle_settings_input(vk, user_id, text, state)
        return

    # Обработка ввода города для погоды
    if state.get("state") == "weather_setting_city":
        handle_weather_city_input(vk, user_id, text, state)
        return

    # Обработка ввода времени для погоды
    if state.get("state") == "weather_setting_time":
        handle_weather_time_input(vk, user_id, text, state)
        return

    # Обработка добавления рецепта
    if state.get("state") == "adding_recipe":
        handle_recipe_ingredient_input(vk, user_id, text, state)
        return

    # Обработка добавления описания рецепта
    if state.get("state") == "adding_description":
        handle_recipe_description_input(vk, user_id, text, state)
        return

    # Обработка редактирования элемента
    if state.get("state") == "editing_item":
        handle_item_edit_input(vk, user_id, text, state)
        return

    # Обработка создания/редактирования пользовательских категорий
    if state.get("state") in ["custom_category_creating", "custom_category_editing"]:
        handle_custom_category_input(vk, user_id, text, state)
        return

    # Обработка триггерных слов
    settings = run_async(db.get_category_settings(user_id))

    buy_trigger = settings.get('buy_trigger', 'купить')
    todo_trigger = settings.get('todo_trigger', 'сделать')
    study_trigger = settings.get('study_trigger', 'учёба')
    ideas_trigger = settings.get('ideas_trigger', 'идея')
    recipes_trigger = settings.get('recipes_trigger', 'рецепт')

    buy_trigger_lower = buy_trigger.lower()
    todo_trigger_lower = todo_trigger.lower()
    study_trigger_lower = study_trigger.lower()
    ideas_trigger_lower = ideas_trigger.lower()
    recipes_trigger_lower = recipes_trigger.lower()

    # Проверяем префиксы категорий
    manual_category = None
    magnit_prefixes = [f"{settings['magnit_name'].lower()} ", f"{settings['magnit_short'].lower()} "]
    fixprice_prefixes = [f"{settings['fixprice_name'].lower()} ", f"{settings['fixprice_short'].lower()} "]
    other_prefixes = [f"{settings['other_name'].lower()} ", f"{settings['other_short'].lower()} "]

    for prefix_list, category in [(magnit_prefixes, "magnit"), (fixprice_prefixes, "fixprice"), (other_prefixes, "other")]:
        for prefix in prefix_list:
            if text_lower.startswith(prefix):
                manual_category = category
                text = text[len(prefix):].strip()
                text_lower = text.lower()
                break
        if manual_category:
            break

    # Проверяем триггеры
    if text_lower.startswith(buy_trigger_lower):
        handle_shopping_message(vk, user_id, text, buy_trigger, manual_category, settings)
    elif text_lower.startswith(todo_trigger_lower):
        handle_todo_message(vk, user_id, text, todo_trigger, settings)
    elif text_lower.startswith(study_trigger_lower):
        handle_study_message(vk, user_id, text, study_trigger, settings)
    elif text_lower.startswith(ideas_trigger_lower):
        handle_ideas_message(vk, user_id, text, ideas_trigger, settings)
    elif text_lower.startswith(recipes_trigger_lower):
        handle_recipes_message(vk, user_id, text, recipes_trigger, settings)


def handle_shopping_message(vk, user_id: int, text: str, trigger: str, manual_category: str, settings: dict):
    """Обработка сообщения с покупками."""
    item_text = text[len(trigger):].strip()

    if not item_text:
        send_message(vk, user_id, f"❌ Укажите, что нужно купить.\n\nНапример: {trigger} молоко, яйца, хлеб")
        return

    # Разбиваем по запятой
    items = [item.strip() for item in item_text.split(',')]

    category_names = {
        "magnit": f"🥕 {settings['magnit_name']} ({settings.get('magnit_desc', 'Продукты')})",
        "fixprice": f"🏠 {settings['fixprice_name']} ({settings.get('fixprice_desc', 'Бытовое')})",
        "other": f"📦 {settings['other_name']} ({settings.get('other_desc', 'Другое')})"
    }

    # Загружаем пользовательские категории для отображения названий
    custom_categories = run_async(db.get_custom_categories(user_id))
    custom_cat_names = {}
    for cat in custom_categories:
        custom_cat_names[f"custom_{cat['id']}"] = f"{cat['icon']} {cat['name']} ({cat['description'] or 'Без описания'})"

    added_items = []
    existing_items = []

    for item in items:
        if not item:
            continue
        item = item.capitalize()
        
        # Определяем категорию
        if manual_category:
            category = manual_category
            custom_cat_id = None
        else:
            category, custom_cat_id = classify_item_with_custom(user_id, item)
        
        # Добавляем товар
        if custom_cat_id:
            # Для пользовательских категорий используем custom_<id> как категорию
            db_category = f"custom_{custom_cat_id}"
        else:
            db_category = category
        
        success, status = run_async(db.add_shopping_item(user_id, item, db_category))
        
        # Получаем название категории для отображения
        display_name = custom_cat_names.get(db_category, category_names.get(db_category, db_category))
        
        if success:
            added_items.append(f"{item} → {display_name}")
        else:
            existing_items.append(f"{item} (уже в {display_name})")

    response = ""
    if added_items:
        response = "✅ Добавлено:\n" + "\n".join(f"• {item}" for item in added_items)
    if existing_items:
        if response:
            response += "\n\n"
        response += "⚠️ Уже есть в списке:\n" + "\n".join(f"• {item}" for item in existing_items)

    send_message(vk, user_id, response)


def handle_todo_message(vk, user_id: int, text: str, trigger: str, settings: dict):
    """Обработка сообщения с делами."""
    task_text = text[len(trigger):].strip()
    cleaned_text, due_date = parse_date_from_text(task_text)

    if not cleaned_text:
        send_message(vk, user_id, f"❌ Задача не может быть пустой.\n\nНапример: {trigger} уборку завтра")
        return

    cleaned_text = cleaned_text.capitalize()

    success, status = run_async(db.add_todo_item(user_id, cleaned_text, due_date))

    if success:
        response = f"✅ Задача добавлена: {cleaned_text}"
        if due_date:
            days_until = (due_date - date.today()).days
            if days_until == 0:
                response += "\n📅 Срок: сегодня"
            elif days_until == 1:
                response += "\n📅 Срок: завтра"
            else:
                response += f"\n📅 Срок: {due_date.strftime('%d.%m.%Y')}"
    else:
        response = f"⚠️ Такая задача уже есть: {cleaned_text}"

    send_message(vk, user_id, response)


def handle_study_message(vk, user_id: int, text: str, trigger: str, settings: dict):
    """Обработка сообщения с учёбой."""
    task_text = text[len(trigger):].strip()

    if not task_text:
        send_message(vk, user_id, f"❌ Задача не может быть пустой.\n\nНапример: {trigger} выучить 50 слов")
        return

    task_text = task_text.capitalize()

    success, status = run_async(db.add_study_item(user_id, task_text))

    if success:
        send_message(vk, user_id, f"✅ Добавлено в учёбу: {task_text}")
    else:
        send_message(vk, user_id, f"⚠️ Такая задача уже есть: {task_text}")


def handle_ideas_message(vk, user_id: int, text: str, trigger: str, settings: dict):
    """Обработка сообщения с идеями."""
    idea_text = text[len(trigger):].strip()

    if not idea_text:
        send_message(vk, user_id, f"❌ Идея не может быть пустой.\n\nНапример: {trigger} записать мысль")
        return

    idea_text = idea_text.capitalize()

    success, status = run_async(db.add_idea(user_id, idea_text))

    if success:
        send_message(vk, user_id, f"✅ Добавлено в идеи: {idea_text}")
    else:
        send_message(vk, user_id, f"⚠️ Такая идея уже есть: {idea_text}")


def handle_recipes_message(vk, user_id: int, text: str, trigger: str, settings: dict):
    """Обработка сообщения с рецептами."""
    recipe_text = text[len(trigger):].strip()

    if not recipe_text:
        send_message(vk, user_id, f"❌ Укажите название рецепта.\n\nНапример: {trigger} Борщ")
        return

    # Запускаем процесс добавления рецепта
    set_user_state(user_id, "adding_recipe", {"recipe_name": recipe_text, "ingredients": []})
    send_message(vk, user_id, (
        f"🍳 Добавляем рецепт: {recipe_text}\n\n"
        f"Добавьте ингредиенты по одному:\n"
        f"Напишите ингредиент (например, молоко 500мл или яйца 6шт).\n\n"
        f"Когда закончите, напишите готово или /done.\n"
        f"Для отмены: /cancel"
    ))


def handle_recipe_ingredient_input(vk, user_id: int, text: str, state: dict):
    """Обработка ввода ингредиента рецепта."""
    text = text.strip()
    text_lower = text.lower()

    # Проверяем на "готово"
    if text_lower in ["готово", "done", "/done"]:
        handle_done(vk, user_id)
        return

    data = state.get("data", {})
    recipe_name = data.get("recipe_name")
    ingredients = data.get("ingredients", [])

    # Добавляем ингредиент
    ingredients.append(text)
    set_user_state(user_id, "adding_recipe", {"recipe_name": recipe_name, "ingredients": ingredients})

    send_message(vk, user_id, (
        f"✅ Добавлено: {text}\n\n"
        f"Уже добавлено: {len(ingredients)}\n\n"
        f"Добавляйте остальные ингредиенты по одному.\n"
        f"Когда закончите, напишите готово или /done."
    ))


def handle_recipe_description_input(vk, user_id: int, text: str, state: dict):
    """Обработка ввода описания рецепта."""
    text = text.strip()
    text_lower = text.lower()

    # Проверяем на "пропустить"
    if text_lower in ["пропустить", "skip", "/skip"]:
        description = None
    else:
        description = text

    data = state.get("data", {})
    recipe_name = data.get("recipe_name")
    ingredients = data.get("ingredients", [])

    recipe_id, status = run_async(db.add_recipe(user_id, recipe_name, description))

    if status == "already_exists":
        clear_user_state(user_id)
        settings = run_async(db.get_category_settings(user_id))
        send_message(vk, user_id, f"⚠️ Рецепт «{recipe_name}» уже есть в списке.", keyboard=get_main_keyboard(settings))
        return

    # Добавляем ингредиенты
    for ingredient in ingredients:
        run_async(db.add_recipe_ingredient(recipe_id, ingredient))

    clear_user_state(user_id)

    response = f"✅ Рецепт {recipe_name} сохранён!\n"
    response += f"Ингредиенты: {len(ingredients)} шт.\n"
    if description:
        response += "Описание: добавлено\n"
    response += "\nРецепт доступен в разделе 🍳 Рецепты."

    settings = run_async(db.get_category_settings(user_id))
    send_message(vk, user_id, response, keyboard=get_main_keyboard(settings))


def handle_settings_input(vk, user_id: int, text: str, state: dict):
    """Обработка ввода для настроек."""
    text = text.strip()
    data = state.get("data", {})
    editing_what = data.get("editing_what")
    category = data.get("category")
    trigger_type = data.get("trigger_type")

    if not editing_what:
        clear_user_state(user_id)
        return

    if editing_what == "name":
        if len(text) > 20:
            send_message(vk, user_id, "❌ Название слишком длинное (максимум 20 символов). Попробуйте ещё раз:")
            return
        run_async(db.update_category_settings(user_id, **{f'{category}_name': text}))
        send_message(vk, user_id, f"✅ Название обновлено: {text}")
    elif editing_what == "desc":
        if len(text) > 30:
            send_message(vk, user_id, "❌ Описание слишком длинное (максимум 30 символов). Попробуйте ещё раз:")
            return
        run_async(db.update_category_settings(user_id, **{f'{category}_desc': text}))
        send_message(vk, user_id, f"✅ Описание обновлено: {text}")
    elif editing_what == "short":
        if len(text) != 1:
            send_message(vk, user_id, "❌ Сокращение должно быть одной буквой. Попробуйте ещё раз:")
            return
        run_async(db.update_category_settings(user_id, **{f'{category}_short': text}))
        send_message(vk, user_id, f"✅ Сокращение обновлено: {text}")
    elif editing_what == "trigger":
        if len(text) > 15:
            send_message(vk, user_id, "❌ Команда слишком длинная (максимум 15 символов). Попробуйте ещё раз:")
            return
        run_async(db.update_category_settings(user_id, **{f'{trigger_type}_trigger': text}))
        send_message(vk, user_id, f"✅ Команда обновлена: {text}")
    elif editing_what == "city":
        run_async(db.update_category_settings(user_id, weather_city=text))
        send_message(vk, user_id, f"✅ Город установлен: {text}")
    elif editing_what == "time":
        # Проверяем формат времени
        time_match = re.match(r'^([0-9]{1,2}):([0-5][0-9])$', text)
        if not time_match:
            send_message(vk, user_id, "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 06:00, 8:30):")
            return
        hour = int(time_match.group(1))
        if hour > 23:
            send_message(vk, user_id, "❌ Часы должны быть от 0 до 23:")
            return
        normalized_time = f"{hour:02d}:{int(time_match.group(2)):02d}"
        run_async(db.update_category_settings(user_id, weather_time=normalized_time))
        send_message(vk, user_id, f"✅ Время отправки установлено: {normalized_time}")

    clear_user_state(user_id)
    handle_settings_button(vk, user_id)


def handle_weather_city_input(vk, user_id: int, text: str, state: dict):
    """Установка города для погоды."""
    city = text.strip()

    # Сохраняем город без проверки API (пользователь сам знает свой город)
    run_async(db.update_category_settings(user_id, weather_city=city))

    clear_user_state(user_id)
    
    # Пробуем получить погоду для отображения
    weather = run_async(get_weather(city))
    if weather.get("success"):
        send_message(vk, user_id, f"✅ Город установлен: {city}\n\n🌡 Сейчас: +{weather['temp']}°C, {weather['description']}")
    else:
        send_message(vk, user_id, f"✅ Город установлен: {city}\n\n⚠️ Не удалось получить погоду (проверьте API ключ или название города)")
    
    handle_settings_button(vk, user_id)


def handle_custom_category_input(vk, user_id: int, text: str, state: dict):
    """Обработка ввода при создании/редактировании пользовательской категории."""
    text = text.strip()

    # Проверяем отмену
    if text.lower() == '/cancel':
        clear_user_state(user_id)
        send_message(vk, user_id, "❌ Действие отменено.")
        handle_categories(vk, user_id)
        return

    if not text:
        send_message(vk, user_id, "❌ Значение не может быть пустым. Попробуйте ещё раз:")
        return

    state_name = state.get("state")

    # Создание новой категории
    if state_name == "custom_category_creating":
        data = state.get("data", {})
        step = data.get("step")

        if step == "name":
            if len(text) > 30:
                send_message(vk, user_id, "❌ Название слишком длинное (максимум 30 символов). Попробуйте ещё раз:")
                return

            set_user_state(user_id, "custom_category_creating", {
                "step": "short",
                "name": text
            })
            send_message(vk, user_id, (
                f"✅ Название: {text}\n\n"
                f"Теперь введите сокращение (1-2 буквы):\n"
                f"(например: п, мк, dns)\n\n"
                f"Для отмены: /cancel"
            ))

        elif step == "short":
            if len(text) > 3:
                send_message(vk, user_id, "❌ Сокращение слишком длинное (максимум 3 буквы). Попробуйте ещё раз:")
                return

            set_user_state(user_id, "custom_category_creating", {
                "step": "description",
                "name": data.get("name"),
                "short": text
            })
            send_message(vk, user_id, (
                f"✅ Сокращение: {text}\n\n"
                f"Введите описание категории (необязательно):\n"
                f"(например: Продукты, Бытовое, Электроника)\n"
                f"Чтобы пропустить, напишите: пропустить\n\n"
                f"Для отмены: /cancel"
            ))

        elif step == "description":
            description = text if text.lower() != "пропустить" else ""

            set_user_state(user_id, "custom_category_creating", {
                "step": "keywords",
                "name": data.get("name"),
                "short": data.get("short"),
                "description": description
            })
            send_message(vk, user_id, (
                f"✅ Описание: {description or 'пропущено'}\n\n"
                f"Введите ключевые слова для автоклассификации:\n"
                f"(через запятую, например: молоко,хлеб,сыр)\n"
                f"Чтобы пропустить, напишите: пропустить\n\n"
                f"Для отмены: /cancel"
            ))

        elif step == "keywords":
            keywords = text if text.lower() != "пропустить" else ""

            set_user_state(user_id, "custom_category_creating", {
                "step": "icon",
                "name": data.get("name"),
                "short": data.get("short"),
                "description": data.get("description"),
                "keywords": keywords
            })
            send_message(vk, user_id, (
                f"✅ Ключевые слова: {keywords or 'пропущены'}\n\n"
                f"Введите иконку (эмодзи):\n"
                f"(например: 🛒, 🏪, 💻)\n"
                f"Чтобы использовать 📦, напишите: пропустить\n\n"
                f"Для отмены: /cancel"
            ))

        elif step == "icon":
            icon = text if text.lower() != "пропустить" else "📦"

            # Создаём категорию
            name = data.get("name")
            short = data.get("short")
            description = data.get("description", "")
            keywords = data.get("keywords", "")

            success, status = run_async(db.add_custom_category(
                user_id, name, short, description, keywords, icon
            ))

            clear_user_state(user_id)

            if success:
                send_message(vk, user_id, (
                    f"✅ Категория «{name}» создана!\n\n"
                    f"{icon} **{name}** (`{short}`)\n"
                    f"Описание: {description or 'не задано'}\n"
                    f"Ключевые слова: {keywords or 'не заданы'}\n\n"
                    f"Теперь товары с этими ключевыми словами\n"
                    f"будут автоматически попадать в эту категорию."
                ))
                handle_categories(vk, user_id)
            else:
                send_message(vk, user_id, f"⚠️ Категория «{name}» уже существует.")
                handle_categories(vk, user_id)

    # Редактирование существующей категории
    elif state_name == "custom_category_editing":
        data = state.get("data", {})
        category_id = data.get("category_id")
        field = data.get("field")

        # Ограничения по длине
        if field == "name" and len(text) > 30:
            send_message(vk, user_id, "❌ Название слишком длинное (максимум 30 символов). Попробуйте ещё раз:")
            return
        elif field == "short" and len(text) > 3:
            send_message(vk, user_id, "❌ Сокращение слишком длинное (максимум 3 буквы). Попробуйте ещё раз:")
            return

        success = run_async(db.update_custom_category(user_id, category_id, **{field: text}))

        clear_user_state(user_id)

        if success:
            send_message(vk, user_id, f"✅ Поле обновлено!")
            handle_categories(vk, user_id)
        else:
            send_message(vk, user_id, "❌ Ошибка обновления.")
            handle_categories(vk, user_id)


def handle_weather_time_input(vk, user_id: int, text: str, state: dict):
    """Установка времени для погоды."""
    time_text = text.strip()

    time_match = re.match(r'^([0-9]{1,2}):([0-5][0-9])$', time_text)
    if not time_match:
        send_message(vk, user_id, "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 06:00, 8:30):")
        return

    hour = int(time_match.group(1))
    if hour > 23:
        send_message(vk, user_id, "❌ Часы должны быть от 0 до 23:")
        return

    normalized_time = f"{hour:02d}:{int(time_match.group(2)):02d}"

    run_async(db.update_category_settings(user_id, weather_time=normalized_time))

    clear_user_state(user_id)
    send_message(vk, user_id, f"✅ Время отправки установлено: {normalized_time}")
    handle_settings_button(vk, user_id)


def handle_item_edit_input(vk, user_id: int, text: str, state: dict):
    """Обработка ввода при редактировании элемента."""
    text = text.strip()

    # Проверяем отмену
    if text.lower() == '/cancel':
        clear_user_state(user_id)
        settings = run_async(db.get_category_settings(user_id))
        send_message(vk, user_id, "❌ Редактирование отменено.", keyboard=get_main_keyboard(settings))
        return

    if not text:
        send_message(vk, user_id, "❌ Текст не может быть пустым. Введите новый текст:")
        return

    data = state.get("data", {})
    list_type = data.get("editing_list_type")
    item_id = data.get("editing_item_id")

    # Обновляем элемент в базе
    if list_type == "todo":
        run_async(db.update_todo_item(user_id, item_id, text))
        message = f"✅ Задача обновлена:\n{text}"
    elif list_type == "study":
        run_async(db.update_study_item(user_id, item_id, text))
        message = f"✅ Учебная задача обновлена:\n{text}"
    elif list_type == "ideas":
        run_async(db.update_idea(user_id, item_id, text))
        message = f"✅ Идея обновлена:\n{text}"
    else:
        message = "✅ Элемент обновлен."

    clear_user_state(user_id)
    settings = run_async(db.get_category_settings(user_id))
    send_message(vk, user_id, message, keyboard=get_main_keyboard(settings))


# ============================================================
# === ОБРАБОТКА CALLBACK (Inline кнопки)
# ============================================================

def handle_callback(vk, event):
    """Обработка нажатий на inline кнопки."""
    user_id = event.obj.user_id
    peer_id = event.obj.peer_id
    conversation_message_id = event.obj.conversation_message_id

    # payload может быть dict (уже распарсен) или строкой
    payload = event.obj.payload
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except:
            return

    action_type = payload.get("type")

    # Игнорируем noop
    if action_type == "noop":
        return

    # Навигация
    if action_type == "back_to_main":
        clear_user_state(user_id)
        settings = run_async(db.get_category_settings(user_id))
        send_message(vk, user_id, "🏠 ГЛАВНОЕ МЕНЮ\n\nВыберите раздел:", keyboard=get_main_keyboard(settings))

    elif action_type == "back_to_shopping":
        handle_shopping_button(vk, user_id)

    elif action_type == "back_to_recipes":
        handle_recipes_view(vk, user_id)

    # Покупки
    elif action_type == "shopping":
        category = payload.get("category")
        settings = run_async(db.get_category_settings(user_id))

        items = run_async(db.get_shopping_items(user_id, category))
    
        category_names = {
            "magnit": f"🥕 {settings['magnit_name']} ({settings.get('magnit_desc', 'Продукты')})",
            "fixprice": f"🏠 {settings['fixprice_name']} ({settings.get('fixprice_desc', 'Бытовое')})",
            "other": f"📦 {settings['other_name']} ({settings.get('other_desc', 'Другое')})"
        }

        if not items:
            message = f"{category_names[category]}\n\nСписок пуст."
            keyboard = get_inline_keyboard([[{"text": "🔙 Назад к категориям", "color": "secondary", "payload": {"type": "back_to_shopping"}}]])
        else:
            message = f"{category_names[category]}:\n\n"
            for item in items:
                if item['taken']:
                    message += f"✅ {item['item']}\n"
                else:
                    message += f"• {item['item']}\n"
            message += f"\nВсего: {len(items)}"
            keyboard = get_items_keyboard("shopping", category, settings)

        send_message(vk, user_id, message, keyboard=keyboard)

    # Редактирование списка
    elif action_type == "edit_list":
        list_type = payload.get("list_type")
        category = payload.get("category")
        settings = run_async(db.get_category_settings(user_id))

        if list_type == "shopping":
            items = run_async(db.get_shopping_items(user_id, category))
        elif list_type == "todo":
            items = run_async(db.get_todo_items(user_id))
        elif list_type == "study":
            items = run_async(db.get_study_items(user_id))
        elif list_type == "ideas":
            items = run_async(db.get_ideas(user_id))
        else:
            items = []

    
        keyboard = get_edit_keyboard(items, list_type, category, settings)

        # Формируем текст
        if list_type == "shopping":
            category_names = {
                "magnit": f"🥕 {settings['magnit_name']}",
                "fixprice": f"🏠 {settings['fixprice_name']}",
                "other": f"📦 {settings['other_name']}"
            }
            message = f"{category_names.get(category, category)}:\n\n"
            for item in items:
                taken_status = "✅" if item['taken'] else "❌"
                message += f"{taken_status} {item['item']}\n"
        elif list_type == "todo":
            message = "📋 Список дел:\n\n"
            for item in items:
                message += f"❌ {item['task']}\n"
        elif list_type == "study":
            message = "📚 Учёба:\n\n"
            for item in items:
                message += f"❌ {item['task']}\n"
        elif list_type == "ideas":
            message = "💡 Идеи:\n\n"
            for item in items:
                message += f"✨ {item['idea']}\n"
        else:
            message = "Список пуст."

        message += f"\nВсего: {len(items)}"

        send_message(vk, user_id, message, keyboard=keyboard)

    # Переключение статуса товара
    elif action_type == "toggle_item":
        list_type = payload.get("list_type")
        item_id = payload.get("item_id")
        category = payload.get("category")

        if list_type == "shopping":
            is_taken = run_async(db.toggle_shopping_item_taken(user_id, item_id))

            # Обновляем список
            settings = run_async(db.get_category_settings(user_id))
            items = run_async(db.get_shopping_items(user_id, category))
        
            keyboard = get_edit_keyboard(items, "shopping", category, settings)

            category_names = {
                "magnit": f"🥕 {settings['magnit_name']}",
                "fixprice": f"🏠 {settings['fixprice_name']}",
                "other": f"📦 {settings['other_name']}"
            }
            message = f"{category_names.get(category, category)}:\n\n"
            for item in items:
                taken_status = "✅" if item['taken'] else "❌"
                message += f"{taken_status} {item['item']}\n"
            message += f"\nВсего: {len(items)}"

            send_message(vk, user_id, message, keyboard=keyboard)

    # Редактирование элемента
    elif action_type == "edit_item":
        list_type = payload.get("list_type")
        item_id = payload.get("item_id")
        category = payload.get("category")

        # Получаем элемент для редактирования
        if list_type == "todo":
            items = run_async(db.get_todo_items(user_id))
            item = next((i for i in items if i['id'] == item_id), None)
            if item:
                set_user_state(user_id, "editing_item", {
                    "editing_list_type": list_type,
                    "editing_item_id": item_id,
                    "old_text": item['task']
                })
                send_message(vk, user_id, (
                    f"✏️ Редактирование задачи:\n\n"
                    f"Текущий текст: {item['task']}\n\n"
                    f"Введите новый текст задачи:\n"
                    f"(для отмены: /cancel)"
                ))
        elif list_type == "study":
            items = run_async(db.get_study_items(user_id))
            item = next((i for i in items if i['id'] == item_id), None)
            if item:
                set_user_state(user_id, "editing_item", {
                    "editing_list_type": list_type,
                    "editing_item_id": item_id,
                    "old_text": item['task']
                })
                send_message(vk, user_id, (
                    f"✏️ Редактирование учебной задачи:\n\n"
                    f"Текущий текст: {item['task']}\n\n"
                    f"Введите новый текст задачи:\n"
                    f"(для отмены: /cancel)"
                ))
        elif list_type == "ideas":
            items = run_async(db.get_ideas(user_id))
            item = next((i for i in items if i['id'] == item_id), None)
            if item:
                set_user_state(user_id, "editing_item", {
                    "editing_list_type": list_type,
                    "editing_item_id": item_id,
                    "old_text": item['idea']
                })
                send_message(vk, user_id, (
                    f"✏️ Редактирование идеи:\n\n"
                    f"Текущий текст: {item['idea']}\n\n"
                    f"Введите новый текст идеи:\n"
                    f"(для отмены: /cancel)"
                ))

    # Удаление элемента
    elif action_type == "delete_item":
        list_type = payload.get("list_type")
        item_id = payload.get("item_id")
        category = payload.get("category")

        if list_type == "shopping":
            run_async(db.delete_shopping_item(user_id, item_id))
            items = run_async(db.get_shopping_items(user_id, category))
        elif list_type == "todo":
            run_async(db.delete_todo_item(user_id, item_id))
            items = run_async(db.get_todo_items(user_id))
        elif list_type == "study":
            run_async(db.delete_study_item(user_id, item_id))
            items = run_async(db.get_study_items(user_id))
        elif list_type == "ideas":
            run_async(db.delete_idea(user_id, item_id))
            items = run_async(db.get_ideas(user_id))
        else:
            items = []

    
        settings = run_async(db.get_category_settings(user_id))
        keyboard = get_edit_keyboard(items, list_type, category, settings)

        # Формируем текст
        if list_type == "shopping":
            message = "Список покупок:\n\n"
            for item in items:
                taken_status = "✅" if item['taken'] else "❌"
                message += f"{taken_status} {item['item']}\n"
        elif list_type == "todo":
            message = "📋 Список дел:\n\n"
            for item in items:
                message += f"❌ {item['task']}\n"
        elif list_type == "study":
            message = "📚 Учёба:\n\n"
            for item in items:
                message += f"❌ {item['task']}\n"
        elif list_type == "ideas":
            message = "💡 Идеи:\n\n"
            for item in items:
                message += f"✨ {item['idea']}\n"
        else:
            message = "Список пуст."

        message += f"\nВсего: {len(items)}"

        send_message(vk, user_id, message, keyboard=keyboard)

    # Очистка списка
    elif action_type == "clear_list":
        list_type = payload.get("list_type")
        category = payload.get("category")

        if list_type == "shopping":
            run_async(db.clear_shopping_list(user_id, category))
            message = "✅ Список покупок очищен"
        elif list_type == "todo":
            run_async(db.clear_todo_list(user_id))
            message = "✅ Список дел очищен"
        elif list_type == "study":
            run_async(db.clear_study_list(user_id))
            message = "✅ Список учёбы очищен"
        elif list_type == "ideas":
            run_async(db.clear_ideas_list(user_id))
            message = "✅ Список идей очищен"
        else:
            message = "✅ Список очищен"

    
        settings = run_async(db.get_category_settings(user_id))
        send_message(vk, user_id, message, keyboard=get_main_keyboard(settings))

    # Настройки категорий
    elif action_type == "settings_category":
        category = payload.get("category")
        set_user_state(user_id, "settings_choosing_category", {"category": category})

        settings = run_async(db.get_category_settings(user_id))
        current_name = settings[f'{category}_name']
        current_short = settings[f'{category}_short']
        current_desc = settings.get(f'{category}_desc', 'Описание')

        category_names = {
            'magnit': '🥕 Магнит',
            'fixprice': '🏠 Фикспрайс',
            'other': '📦 Другое'
        }

        buttons = [
            [{
                "text": "✏️ Изменить название",
                "color": "primary",
                "payload": {"type": "settings_edit", "edit_type": "name", "category": category}
            }],
            [{
                "text": "📝 Изменить описание",
                "color": "primary",
                "payload": {"type": "settings_edit", "edit_type": "desc", "category": category}
            }],
            [{
                "text": "🔤 Изменить сокращение",
                "color": "primary",
                "payload": {"type": "settings_edit", "edit_type": "short", "category": category}
            }],
            [{
                "text": "🔙 Назад к настройкам",
                "color": "secondary",
                "payload": {"type": "back_to_settings"}
            }]
        ]

        keyboard = get_inline_keyboard(buttons)

        message = (
            f"{category_names.get(category, 'Магазин')}\n\n"
            f"Название: {current_name}\n"
            f"Описание: {current_desc}\n"
            f"Сокращение: {current_short}\n\n"
            f"Выберите, что хотите изменить:"
        )

        send_message(vk, user_id, message, keyboard=keyboard)

    # Редактирование настроек
    elif action_type == "settings_edit":
        edit_type = payload.get("edit_type")
        category = payload.get("category")

        if edit_type == "name":
            set_user_state(user_id, "settings_editing_name", {"editing_what": "name", "category": category})
            send_message(vk, user_id, "✏️ Новое название магазина\n\nВведите название (1-20 символов):\nНапример: Перекрёсток, Пятёрочка, Ашан\n\nДля отмены: /cancel")
        elif edit_type == "desc":
            set_user_state(user_id, "settings_editing_desc", {"editing_what": "desc", "category": category})
            send_message(vk, user_id, "📝 Новое описание магазина\n\nВведите описание (1-30 символов):\nНапример: Продукты, Бытовое, Электроника\n\nДля отмены: /cancel")
        elif edit_type == "short":
            set_user_state(user_id, "settings_editing_short", {"editing_what": "short", "category": category})
            send_message(vk, user_id, "🔤 Новое сокращение\n\nВведите одну букву:\nНапример: п, ф, д\n\nДля отмены: /cancel")

    # Триггерные слова
    elif action_type == "settings_triggers":
        settings = run_async(db.get_category_settings(user_id))

        buttons = [
            [{
                "text": f"🛒 Покупки: {settings.get('buy_trigger', 'купить')}",
                "color": "primary",
                "payload": {"type": "settings_edit_trigger", "trigger_type": "buy"}
            }],
            [{
                "text": f"📋 Дела: {settings.get('todo_trigger', 'сделать')}",
                "color": "primary",
                "payload": {"type": "settings_edit_trigger", "trigger_type": "todo"}
            }],
            [{
                "text": f"📚 Учёба: {settings.get('study_trigger', 'учёба')}",
                "color": "primary",
                "payload": {"type": "settings_edit_trigger", "trigger_type": "study"}
            }],
            [{
                "text": f"💡 Идеи: {settings.get('ideas_trigger', 'идея')}",
                "color": "primary",
                "payload": {"type": "settings_edit_trigger", "trigger_type": "ideas"}
            }],
            [{
                "text": f"🍳 Рецепты: {settings.get('recipes_trigger', 'рецепт')}",
                "color": "primary",
                "payload": {"type": "settings_edit_trigger", "trigger_type": "recipes"}
            }],
            [{
                "text": "🔙 Назад к настройкам",
                "color": "secondary",
                "payload": {"type": "back_to_settings"}
            }]
        ]

        keyboard = get_inline_keyboard(buttons)

        send_message(vk, user_id, (
            f"🔤 Команды\n\n"
            f"Эти слова используются для добавления записей:\n\n"
            f"🛒 Покупки: {settings.get('buy_trigger', 'купить')}\n"
            f"   Пример: {settings.get('buy_trigger', 'купить')} молоко\n\n"
            f"📋 Дела: {settings.get('todo_trigger', 'сделать')}\n"
            f"   Пример: {settings.get('todo_trigger', 'сделать')} уборку завтра\n\n"
            f"📚 Учёба: {settings.get('study_trigger', 'учёба')}\n"
            f"   Пример: {settings.get('study_trigger', 'учёба')} выучить слова\n\n"
            f"💡 Идеи: {settings.get('ideas_trigger', 'идея')}\n"
            f"   Пример: {settings.get('ideas_trigger', 'идея')} записать мысль\n\n"
            f"🍳 Рецепты: {settings.get('recipes_trigger', 'рецепт')}\n"
            f"   Пример: {settings.get('recipes_trigger', 'рецепт')} Борщ\n\n"
            f"Нажмите на команду, чтобы изменить слово."
        ), keyboard=keyboard)

    elif action_type == "settings_edit_trigger":
        trigger_type = payload.get("trigger_type")
        set_user_state(user_id, "settings_editing_trigger", {"editing_what": "trigger", "trigger_type": trigger_type})

        trigger_names = {
            'buy': 'покупок',
            'todo': 'дел',
            'study': 'учёбы',
            'ideas': 'идей',
            'recipes': 'рецептов'
        }

        send_message(vk, user_id, (
            f"✏️ Новая команда для списка {trigger_names.get(trigger_type, '')}\n\n"
            f"Введите слово для добавления в список (1-15 символов)\n\n"
            f"Для отмены: /cancel"
        ))

    # Видимость кнопок
    elif action_type == "settings_visibility":
        settings = run_async(db.get_category_settings(user_id))

        def get_status(is_visible):
            return "✅ ВКЛ" if is_visible else "❌ ВЫКЛ"

        # Плоский список для компактной клавиатуры
        buttons = [
            {
                "text": f"🛒 Покупки: {get_status(settings.get('visibility_shopping', 1))}",
                "color": "primary",
                "payload": {"type": "settings_toggle", "toggle_type": "shopping"}
            },
            {
                "text": f"📋 Дела: {get_status(settings.get('visibility_todo', 1))}",
                "color": "primary",
                "payload": {"type": "settings_toggle", "toggle_type": "todo"}
            },
            {
                "text": f"📚 Учёба: {get_status(settings.get('visibility_study', 1))}",
                "color": "primary",
                "payload": {"type": "settings_toggle", "toggle_type": "study"}
            },
            {
                "text": f"💡 Идеи: {get_status(settings.get('visibility_ideas', 1))}",
                "color": "primary",
                "payload": {"type": "settings_toggle", "toggle_type": "ideas"}
            },
            {
                "text": f"🍳 Рецепты: {get_status(settings.get('visibility_recipes', 1))}",
                "color": "primary",
                "payload": {"type": "settings_toggle", "toggle_type": "recipes"}
            },
            {
                "text": f"ℹ️ Инфо: {get_status(settings.get('visibility_info', 1))}",
                "color": "primary",
                "payload": {"type": "settings_toggle", "toggle_type": "info"}
            },
            {
                "text": f"🌤 Погода: {get_status(settings.get('weather_button', 1))}",
                "color": "primary",
                "payload": {"type": "settings_toggle", "toggle_type": "weather"}
            },
            {
                "text": "🔙 Назад",
                "color": "secondary",
                "payload": {"type": "back_to_settings"}
            }
        ]

        keyboard = get_compact_inline_keyboard(buttons)

        send_message(vk, user_id, (
            f"📱 Кнопки главного меню\n\n"
            f"Включите разделы, которыми пользуетесь,\n"
            f"и отключите те, которые не нужны:\n\n"
            f"🛒 Покупки — {get_status(settings.get('visibility_shopping', 1))}\n"
            f"📋 Дела — {get_status(settings.get('visibility_todo', 1))}\n"
            f"📚 Учёба — {get_status(settings.get('visibility_study', 1))}\n"
            f"💡 Идеи — {get_status(settings.get('visibility_ideas', 1))}\n"
            f"🍳 Рецепты — {get_status(settings.get('visibility_recipes', 1))}\n"
            f"ℹ️ Инфо — {get_status(settings.get('visibility_info', 1))}\n"
            f"🌤 Погода — {get_status(settings.get('weather_button', 1))}\n\n"
            f"Нажмите на раздел, чтобы включить или выключить его."
        ), keyboard=keyboard)

    elif action_type == "settings_toggle":
        toggle_type = payload.get("toggle_type")

        visibility_map = {
            'shopping': 'visibility_shopping',
            'todo': 'visibility_todo',
            'study': 'visibility_study',
            'ideas': 'visibility_ideas',
            'recipes': 'visibility_recipes',
            'info': 'visibility_info',
            'weather': 'weather_button'
        }

        if toggle_type in visibility_map:
            settings = run_async(db.get_category_settings(user_id))
            current_value = settings.get(visibility_map[toggle_type], 1)
            new_value = 0 if current_value else 1

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            run_async(db.update_category_settings(user_id, **{visibility_map[toggle_type]: new_value}))
        
            status = "✅ ВКЛЮЧЕНО" if new_value else "❌ ВЫКЛЮЧЕНО"
            send_message(vk, user_id, f"{toggle_type}: {status}")

            # Показываем снова меню видимости
            handle_callback(vk, type('obj', (object,), {'obj': type('obj', (object,), {'user_id': user_id, 'peer_id': peer_id, 'conversation_message_id': conversation_message_id, 'payload': json.dumps({"type": "settings_visibility"})})})())

    # Погода
    elif action_type == "settings_weather":
        settings = run_async(db.get_category_settings(user_id))
        city = settings.get('weather_city', '') or 'не задан'
        daily_status = "✅ ВКЛ" if settings.get('weather_daily', 0) else "❌ ВЫКЛ"
        rain_status = "✅ ВКЛ" if settings.get('weather_rain', 1) else "❌ ВЫКЛ"
        weather_time = settings.get('weather_time', '06:00')

        buttons = [
            [{
                "text": f"🏙 Город: {city}",
                "color": "primary",
                "payload": {"type": "weather_set_city"}
            }],
            [{
                "text": f"🕐 Время отправки: {weather_time}",
                "color": "primary",
                "payload": {"type": "weather_set_time"}
            }],
            [{
                "text": f"📅 Утренний прогноз: {daily_status}",
                "color": "primary",
                "payload": {"type": "weather_toggle_daily"}
            }],
            [{
                "text": f"☂️ Уведомление о дожде: {rain_status}",
                "color": "primary",
                "payload": {"type": "weather_toggle_rain"}
            }],
            [{
                "text": "🔙 Назад к настройкам",
                "color": "secondary",
                "payload": {"type": "back_to_settings"}
            }]
        ]

        keyboard = get_inline_keyboard(buttons)

        send_message(vk, user_id, (
            f"🌤 Настройки погоды\n\n"
            f"🏙 Город: {city}\n"
            f"🕐 Время отправки: {weather_time}\n\n"
            f"📅 Утренний прогноз: {daily_status}\n"
            f"   Ежедневно в настроенное время будет приходить прогноз погоды\n\n"
            f"☂️ Уведомление о дожде: {rain_status}\n"
            f"   При дожде придёт предупреждение с зонтиком\n\n"
            f"⚠️ Уведомления выключены по умолчанию.\n"
            f"Включите их, чтобы получать прогнозы!"
        ), keyboard=keyboard)

    elif action_type == "weather_set_city":
        set_user_state(user_id, "weather_setting_city")
        send_message(vk, user_id, "🏙 Введите название города\n\nНапишите город, для которого хотите получать прогноз:\nНапример: Москва, Санкт-Петербург, Киев\n\nДля отмены: /cancel")

    elif action_type == "weather_set_time":
        set_user_state(user_id, "weather_setting_time")
        settings = run_async(db.get_category_settings(user_id))
        current_time = settings.get('weather_time', '06:00')
        send_message(vk, user_id, (
            f"🕐 Время отправки прогноза\n\n"
            f"Текущее время: {current_time}\n\n"
            f"Введите время в формате ЧЧ:ММ:\n"
            f"Например: 07:00, 08:30, 20:00\n\n"
            f"Для отмены: /cancel"
        ))

    elif action_type == "weather_toggle_daily":
        settings = run_async(db.get_category_settings(user_id))
        new_value = 0 if settings.get('weather_daily', 0) else 1
        run_async(db.update_category_settings(user_id, weather_daily=new_value))
        status = "✅ ВКЛЮЧЕНО" if new_value else "❌ ВЫКЛЮЧЕНО"
        send_message(vk, user_id, f"📅 Прогноз погоды: {status}")

    elif action_type == "weather_toggle_rain":
        settings = run_async(db.get_category_settings(user_id))
        new_value = 0 if settings.get('weather_rain', 1) else 1
        run_async(db.update_category_settings(user_id, weather_rain=new_value))
        status = "✅ ВКЛЮЧЕНО" if new_value else "❌ ВЫКЛЮЧЕНО"
        send_message(vk, user_id, f"☂️ Уведомление о дожде: {status}")

    # Сброс профиля
    elif action_type == "settings_reset_profile":
        buttons = [
            [
                {
                    "text": "⚠️ ДА, сбросить всё!",
                    "color": "negative",
                    "payload": {"type": "reset_profile_confirm"}
                },
                {
                    "text": "❌ Нет, отмена",
                    "color": "secondary",
                    "payload": {"type": "reset_profile_cancel"}
                }
            ],
            [{
                "text": "🔙 Назад в настройки",
                "color": "secondary",
                "payload": {"type": "back_to_settings"}
            }]
        ]

        keyboard = get_inline_keyboard(buttons)

        send_message(vk, user_id, (
            f"⚠️ ВНИМАНИЕ! Сброс профиля!\n\n"
            f"Это действие удалит:\n"
            f"🗑 Все товары из списка покупок\n"
            f"🗑 Все задачи из списка дел\n"
            f"🗑 Все учебные задачи\n"
            f"🗑 Все идеи\n"
            f"🗑 Все рецепты с ингредиентами\n"
            f"🗑 Все настройки (названия магазинов, триггеры, погода)\n\n"
            f"Вы уверены? Это действие НЕОБРАТИМО!"
        ), keyboard=keyboard)

    elif action_type == "reset_profile_confirm":
        run_async(db.reset_user_profile(user_id))
    
        clear_user_state(user_id)
        send_message(vk, user_id, (
            f"✅ Профиль сброшен!\n\n"
            f"Все данные и настройки удалены.\n"
            f"Теперь бот как новый - настройте его под себя!\n\n"
            f"Напишите /start для начала работы."
        ))

    elif action_type == "reset_profile_cancel":
        send_message(vk, user_id, "❌ Сброс отменён")

    elif action_type == "back_to_settings":
        clear_user_state(user_id)
        handle_settings_button(vk, user_id)

    # Админ-панель
    elif action_type == "admin_my_stats":
        if not is_admin(user_id):
            send_message(vk, user_id, "❌ Доступ запрещён.")
            return

        stats = run_async(db.get_user_stats(user_id))
        message = (
            f"📊 **Ваша статистика:**\n\n"
            f"🛒 Товаров в покупках: {stats['shopping_count']}\n"
            f"📋 Задач в делах: {stats['todo_count']}\n"
            f"📚 Учебных задач: {stats['study_count']}\n"
            f"💡 Идей: {stats['ideas_count']}\n"
            f"🍳 Рецептов: {stats['recipes_count']}"
        )

        # Создаём клавиатуру для возврата в админ-панель
        buttons = [[
            {
                "text": "🔙 Назад в админ-панель",
                "color": "secondary",
                "payload": {"type": "back_to_admin"}
            }
        ]]
        keyboard = get_inline_keyboard(buttons)
        send_message(vk, user_id, message, keyboard=keyboard)

    elif action_type == "admin_clear_my_stats":
        if not is_admin(user_id):
            send_message(vk, user_id, "❌ Доступ запрещён.")
            return

        # Очищаем всю статистику пользователя
        run_async(db.clear_shopping_list(user_id))
        run_async(db.clear_todo_list(user_id))
        run_async(db.clear_study_list(user_id))
        run_async(db.clear_ideas_list(user_id))

        # Удаляем рецепты пользователя
        async def clear_user_recipes(uid):
            async with aiosqlite.connect(db.DB_PATH) as db_conn:
                # Удаляем ингредиенты рецептов
                await db_conn.execute("""
                    DELETE FROM recipe_ingredients
                    WHERE recipe_id IN (SELECT id FROM recipes WHERE user_id = ?)
                """, (uid,))
                # Удаляем рецепты
                await db_conn.execute("DELETE FROM recipes WHERE user_id = ?", (uid,))
                await db_conn.commit()

        run_async(clear_user_recipes(user_id))

        message = "✅ Ваша статистика очищена."

        buttons = [[
            {
                "text": "🔙 Назад в админ-панель",
                "color": "secondary",
                "payload": {"type": "back_to_admin"}
            }
        ]]
        keyboard = get_inline_keyboard(buttons)
        send_message(vk, user_id, message, keyboard=keyboard)

    elif action_type == "admin_update_bot":
        if not is_admin(user_id):
            send_message(vk, user_id, "❌ Доступ запрещён.")
            return

        send_message(vk, user_id, (
            f"🔄 **Обновление бота**\n\n"
            f"Версия: {BOT_VERSION}\n\n"
            f"Для обновления используйте команду:\n"
            f"`/update` в чате с ботом\n"
            f"или `vkactl update` на сервере\n\n"
            f"💡 Бот перезапускается автоматически после обновления."
        ))

    elif action_type == "admin_console_commands":
        if not is_admin(user_id):
            send_message(vk, user_id, "❌ Доступ запрещён.")
            return

        message = (
            f"📋 **Команды управления (сервер)**\n\n"
            f"Эти команды работают в консоли сервера:\n\n"
            f"`vkactl status` — статус бота\n"
            f"`vkactl logs` — логи в реальном времени\n"
            f"`vkactl restart` — перезапуск\n"
            f"`vkactl update` — обновление из Git\n"
            f"`vkactl edit` — редактировать .env\n"
            f"`vkactl delete` — полное удаление\n"
            f"`vkactl version` — версия бота\n\n"
            f"🔧 **vkactl edit** позволяет менять:\n"
            f"• ID сообщества (VK_GROUP_ID)\n"
            f"• Токен VK (VK_TOKEN)\n"
            f"• API ключ погоды (WEATHER_API_KEY)\n"
            f"• Admin ID (ADMIN_ID)\n"
            f"• .env файл вручную (nano)\n\n"
            f"После изменений бот перезапускается автоматически."
        )

        buttons = [[
            {
                "text": "🔙 Назад в админ-панель",
                "color": "secondary",
                "payload": {"type": "back_to_admin"}
            }
        ]]
        keyboard = get_inline_keyboard(buttons)
        send_message(vk, user_id, message, keyboard=keyboard)

    elif action_type == "back_to_admin":
        if not is_admin(user_id):
            send_message(vk, user_id, "❌ Доступ запрещён.")
            return
        handle_admin(vk, user_id)

    # Пользовательские категории
    elif action_type == "custom_category_create":
        set_user_state(user_id, "custom_category_creating", {
            "step": "name"
        })
        send_message(vk, user_id, (
            f"➕ **Создание пользовательской категории**\n\n"
            f"Введите название магазина/категории:\n"
            f"(например: Пятёрочка, Магнит Косметик, DNS)\n\n"
            f"Для отмены: /cancel"
        ))

    elif action_type == "custom_category_view":
        category_id = payload.get("category_id")
        category = run_async(db.get_custom_category(user_id, category_id))

        if not category:
            send_message(vk, user_id, "❌ Категория не найдена.")
            return

        message = (
            f"{category['icon']} **{category['name']}**\n\n"
            f"Сокращение: `{category['short']}`\n"
            f"Описание: {category['description'] or 'не задано'}\n"
            f"Ключевые слова: {category['keywords'] or 'не заданы'}\n"
            f"Создана: {category['created_at']}\n\n"
            f"Выберите действие:"
        )

        buttons = [
            [
                {
                    "text": "✏️ Редактировать",
                    "color": "primary",
                    "payload": {"type": "custom_category_edit", "category_id": category_id}
                },
                {
                    "text": "🗑 Удалить",
                    "color": "negative",
                    "payload": {"type": "custom_category_delete", "category_id": category_id}
                }
            ],
            [
                {
                    "text": "🔙 Назад к категориям",
                    "color": "secondary",
                    "payload": {"type": "categories_refresh"}
                }
            ]
        ]

        keyboard = get_inline_keyboard(buttons)
        send_message(vk, user_id, message, keyboard=keyboard)

    elif action_type == "custom_category_edit":
        category_id = payload.get("category_id")
        category = run_async(db.get_custom_category(user_id, category_id))

        if not category:
            send_message(vk, user_id, "❌ Категория не найдена.")
            return

        message = (
            f"✏️ **Редактирование: {category['name']}**\n\n"
            f"Что хотите изменить?"
        )

        buttons = [
            [
                {
                    "text": "📝 Название",
                    "color": "primary",
                    "payload": {"type": "custom_category_edit_field", "category_id": category_id, "field": "name"}
                },
                {
                    "text": "🔤 Сокращение",
                    "color": "primary",
                    "payload": {"type": "custom_category_edit_field", "category_id": category_id, "field": "short"}
                }
            ],
            [
                {
                    "text": "📋 Описание",
                    "color": "primary",
                    "payload": {"type": "custom_category_edit_field", "category_id": category_id, "field": "description"}
                },
                {
                    "text": "🔑 Ключевые слова",
                    "color": "primary",
                    "payload": {"type": "custom_category_edit_field", "category_id": category_id, "field": "keywords"}
                }
            ],
            [
                {
                    "text": "😀 Иконка",
                    "color": "primary",
                    "payload": {"type": "custom_category_edit_field", "category_id": category_id, "field": "icon"}
                }
            ],
            [
                {
                    "text": "🔙 Назад",
                    "color": "secondary",
                    "payload": {"type": "custom_category_view", "category_id": category_id}
                }
            ]
        ]

        keyboard = get_inline_keyboard(buttons)
        send_message(vk, user_id, message, keyboard=keyboard)

    elif action_type == "custom_category_edit_field":
        category_id = payload.get("category_id")
        field = payload.get("field")

        field_names = {
            "name": "название",
            "short": "сокращение",
            "description": "описание",
            "keywords": "ключевые слова",
            "icon": "иконку"
        }

        set_user_state(user_id, "custom_category_editing", {
            "category_id": category_id,
            "field": field
        })

        category = run_async(db.get_custom_category(user_id, category_id))
        current_value = category[field] if category else "не задано"

        send_message(vk, user_id, (
            f"✏️ Введите новое {field_names.get(field, field)}:\n\n"
            f"Текущее значение: {current_value}\n\n"
            f"Для отмены: /cancel"
        ))

    elif action_type == "custom_category_delete":
        category_id = payload.get("category_id")
        category = run_async(db.get_custom_category(user_id, category_id))

        if not category:
            send_message(vk, user_id, "❌ Категория не найдена.")
            return

        buttons = [
            [
                {
                    "text": "✅ Да, удалить",
                    "color": "negative",
                    "payload": {"type": "custom_category_delete_confirm", "category_id": category_id}
                },
                {
                    "text": "❌ Отмена",
                    "color": "secondary",
                    "payload": {"type": "custom_category_view", "category_id": category_id}
                }
            ]
        ]

        keyboard = get_inline_keyboard(buttons)
        send_message(vk, user_id, (
            f"🗑 **Удаление категории**\n\n"
            f"Вы уверены, что хотите удалить «{category['name']}»?\n"
            f"Это действие нельзя отменить."
        ), keyboard=keyboard)

    elif action_type == "custom_category_delete_confirm":
        category_id = payload.get("category_id")
        run_async(db.delete_custom_category(user_id, category_id))
        send_message(vk, user_id, "✅ Категория удалена.")
        handle_categories(vk, user_id)

    elif action_type == "categories_refresh":
        handle_categories(vk, user_id)

    # Рецепты
    elif action_type == "recipe_add_new":
        set_user_state(user_id, "adding_recipe", {"recipe_name": None, "ingredients": []})
        send_message(vk, user_id, (
            f"🍳 Добавление рецепта\n\n"
            f"Напишите название рецепта:\n"
            f"Например: Борщ, Паста Карбонара, Оливье\n\n"
            f"Для отмены: /cancel"
        ))

    elif action_type == "recipe_view":
        recipe_id = payload.get("recipe_id")

        recipe = run_async(db.get_recipe(user_id, recipe_id))
        ingredients = run_async(db.get_recipe_ingredients(recipe_id))
    
        if not recipe:
            send_message(vk, user_id, "❌ Рецепт не найден")
            return

        message = f"🍳 {recipe['name']}\n\n"
        if recipe['description']:
            message += f"Инструкция:\n{recipe['description']}\n\n"

        message += "Ингредиенты:\n"
        if ingredients:
            for ing in ingredients:
                message += f"• {ing['ingredient']}\n"
        else:
            message += "Нет ингредиентов\n"

        buttons = [
            [{
                "text": "🛒 Добавить в корзину",
                "color": "positive",
                "payload": {"type": "recipe_add_to_cart", "recipe_id": recipe_id}
            }],
            [{
                "text": "🗑 Удалить рецепт",
                "color": "negative",
                "payload": {"type": "recipe_delete", "recipe_id": recipe_id}
            }],
            [{
                "text": "🔙 Назад к рецептам",
                "color": "secondary",
                "payload": {"type": "back_to_recipes"}
            }]
        ]

        keyboard = get_inline_keyboard(buttons)
        send_message(vk, user_id, message, keyboard=keyboard)

    elif action_type == "recipe_add_to_cart":
        recipe_id = payload.get("recipe_id")

        ingredients = run_async(db.get_recipe_ingredients(recipe_id))
    
        if not ingredients:
            send_message(vk, user_id, "❌ В рецепте нет ингредиентов")
            return

        settings = run_async(db.get_category_settings(user_id))
        magnit_name = f"🥕 {settings['magnit_name']} ({settings.get('magnit_desc', 'Продукты')})"

        added_items = []
        existing_items = []


        for ing in ingredients:
            ingredient_name = ing['ingredient']
            success, _ = run_async(db.add_shopping_item(user_id, ingredient_name, "magnit"))
            if success:
                added_items.append(f"{ingredient_name} → {magnit_name}")
            else:
                existing_items.append(f"{ingredient_name} (уже в {magnit_name})")

    
        response = "✅ Добавлено в корзину:\n"
        if added_items:
            for item in added_items[:10]:
                response += f"• {item}\n"
            if len(added_items) > 10:
                response += f"... и ещё {len(added_items) - 10}\n"
        else:
            response += "Ничего не добавлено\n"

        if existing_items:
            response += "\n⚠️ Уже есть в списке:\n"
            for item in existing_items[:5]:
                response += f"• {item}\n"
            if len(existing_items) > 5:
                response += f"... и ещё {len(existing_items) - 5}\n"

        send_message(vk, user_id, response)

    elif action_type == "recipe_delete":
        recipe_id = payload.get("recipe_id")

        run_async(db.delete_recipe(user_id, recipe_id))
    
        send_message(vk, user_id, "✅ Рецепт удалён.")

    # Админ-панель
    elif action_type == "admin_panel":
        if not is_admin(user_id):
            send_message(vk, user_id, "❌ Доступ запрещён")
            return


        async def get_stats():
            async with aiosqlite.connect(db.DB_PATH) as db_conn:
                db_conn.row_factory = aiosqlite.Row

                async with db_conn.execute("SELECT COUNT(DISTINCT user_id) FROM shopping_list") as cursor:
                    shopping_users = await cursor.fetchone()
                    shopping_users_count = shopping_users[0] if shopping_users else 0

                async with db_conn.execute("SELECT COUNT(DISTINCT user_id) FROM todo_list") as cursor:
                    todo_users = await cursor.fetchone()
                    todo_users_count = todo_users[0] if todo_users else 0

                async with db_conn.execute("""
                    SELECT COUNT(DISTINCT user_id) FROM (
                        SELECT user_id FROM shopping_list
                        UNION SELECT user_id FROM todo_list
                        UNION SELECT user_id FROM study_list
                        UNION SELECT user_id FROM ideas_list
                        UNION SELECT user_id FROM recipes
                    )
                """) as cursor:
                    total_result = await cursor.fetchone()
                    total_users = total_result[0] if total_result else 0

                async with db_conn.execute("SELECT COUNT(*) FROM shopping_list") as cursor:
                    total_shopping = await cursor.fetchone()
                    total_shopping_count = total_shopping[0] if total_shopping else 0

                async with db_conn.execute("SELECT COUNT(*) FROM todo_list") as cursor:
                    total_todo = await cursor.fetchone()
                    total_todo_count = total_todo[0] if total_todo else 0

                async with db_conn.execute("SELECT COUNT(*) FROM recipes") as cursor:
                    total_recipes = await cursor.fetchone()
                    total_recipes_count = total_recipes[0] if total_recipes else 0

                return {
                    "total_users": total_users,
                    "shopping_users": shopping_users_count,
                    "todo_users": todo_users_count,
                    "total_shopping": total_shopping_count,
                    "total_todo": total_todo_count,
                    "total_recipes": total_recipes_count
                }

        stats = run_async(get_stats())
    
        buttons = [
            [{
                "text": "🔄 Обновить бота",
                "color": "primary",
                "payload": {"type": "admin_update_bot"}
            }],
            [{
                "text": "🔙 Назад в настройки",
                "color": "secondary",
                "payload": {"type": "back_to_settings"}
            }]
        ]

        keyboard = get_inline_keyboard(buttons)

        message = (
            f"👤 Админ-панель\n\n"
            f"📊 Статистика бота:\n\n"
            f"👥 Пользователи:\n"
            f"   • Всего: {stats['total_users']}\n"
            f"   • С покупками: {stats['shopping_users']}\n"
            f"   • С делами: {stats['todo_users']}\n\n"
            f"📝 Записи:\n"
            f"   • Покупки: {stats['total_shopping']}\n"
            f"   • Дела: {stats['total_todo']}\n"
            f"   • Рецепты: {stats['total_recipes']}\n\n"
            f"⚙️ Действия:\n"
            f"Нажмите 'Обновить бота' для проверки и установки обновлений."
        )

        send_message(vk, user_id, message, keyboard=keyboard)

    elif action_type == "admin_update_bot":
        if not is_admin(user_id):
            send_message(vk, user_id, "❌ Доступ запрещён")
            return

        send_message(vk, user_id, "🔄 Проверка обновлений...\n\nПодождите, это может занять несколько минут.")

        try:
            bot_dir = os.path.dirname(os.path.abspath(__file__))
            git_dir = os.path.join(bot_dir, '.git')

            if not os.path.exists(git_dir):
                send_message(vk, user_id, "⚙️ Первичная настройка git...\n\nЭто займёт несколько секунд.")
                subprocess.run(['git', 'init'], cwd=bot_dir, capture_output=True, check=True)
                remote_url = "https://github.com/Drentis/VKAssistant.git"
                subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=bot_dir, capture_output=True, check=True)
                subprocess.run(['git', 'fetch', 'origin'], cwd=bot_dir, capture_output=True, timeout=30, check=True)
                subprocess.run(['git', 'checkout', '-f', 'main'], cwd=bot_dir, capture_output=True, check=True)
                subprocess.run(['git', 'reset', '--hard', 'origin/main'], cwd=bot_dir, capture_output=True, timeout=30, check=True)
                result_stdout = "✓ Репозиторий инициализирован\n✓ Файлы обновлены"
                result_stderr = ""
            else:
                subprocess.run(['git', 'fetch', 'origin'], cwd=bot_dir, capture_output=True, timeout=30, check=True)
                result = subprocess.run(
                    ['git', 'reset', '--hard', 'origin/main'],
                    cwd=bot_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                result_stdout = result.stdout
                result_stderr = result.stderr

            if result_stderr and 'error' in result_stderr.lower():
                send_message(vk, user_id, f"❌ Ошибка обновления:\n{result_stderr[:1000]}")
            else:
                import sys
                if sys.platform == 'win32':
                    pip_path = os.path.join(bot_dir, 'venv', 'Scripts', 'pip.exe')
                else:
                    pip_path = os.path.join(bot_dir, 'venv', 'bin', 'pip')

                subprocess.run(
                    [pip_path, 'install', '-r', os.path.join(bot_dir, 'requirements.txt')],
                    capture_output=True,
                    timeout=120
                )

                send_message(vk, user_id, (
                    f"✅ Бот обновлён!\n\n"
                    f"Обновления применены. Перезапустите бота для применения изменений.\n\n"
                    f"Что изменилось:\n{result_stdout[:1000] if result_stdout else 'Файлы загружены'}"
                ))

        except Exception as e:
            send_message(vk, user_id, f"❌ Произошла ошибка:\n{str(e)}")


# ============================================================
# === ПОГОДА
# ============================================================

async def get_weather(city: str) -> dict:
    """Получить погоду для города."""
    if not WEATHER_API_KEY or WEATHER_API_KEY == "your_api_key_here":
        return {"error": "API ключ не настроен"}

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": WEATHER_API_KEY,
        "units": "metric",
        "lang": "ru"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "temp": round(data["main"]["temp"]),
                        "feels_like": round(data["main"]["feels_like"]),
                        "description": data["weather"][0]["description"],
                        "icon": data["weather"][0]["icon"],
                        "humidity": data["main"]["humidity"],
                        "wind_speed": data["wind"]["speed"],
                        "city": data["name"],
                        "timezone": data.get("timezone", 0)
                    }
                elif response.status == 401:
                    return {"error": "Неверный API ключ"}
                elif response.status == 404:
                    return {"error": "Город не найден"}
                else:
                    return {"error": f"Ошибка API (код {response.status})"}
    except Exception as e:
        return {"error": f"Ошибка: {str(e)}"}


async def send_weather_report(vk, user_id: int, city: str):
    """Отправить отчёт о погоде."""
    weather = await get_weather(city)

    if not weather.get("success"):
        return

    icons = {
        "01d": "☀️", "01n": "🌙",
        "02d": "⛅", "02n": "☁️",
        "03d": "☁️", "03n": "☁️",
        "04d": "☁️", "04n": "☁️",
        "09d": "🌧", "09n": "🌧",
        "10d": "🌦", "10n": "🌧",
        "11d": "⛈", "11n": "⛈",
        "13d": "❄️", "13n": "❄️",
        "50d": "🌫", "50n": "🌫"
    }
    icon = icons.get(weather["icon"], "🌤")

    message = (
        f"{icon} Погода на сегодня\n\n"
        f"📍 {weather['city']}\n"
        f"🌡 +{weather['temp']}°C (ощущается как +{weather['feels_like']}°C)\n"
        f"🌤 {weather['description'].capitalize()}\n"
        f"💨 Ветер {weather['wind_speed']} м/с\n"
        f"💧 Влажность {weather['humidity']}%\n\n"
        f"Хорошего дня! ☀️"
    )

    send_message(vk, user_id, message)


# ============================================================
# === ПЛАНИРОВЩИКИ
# ============================================================

async def send_reminders(vk):
    """Отправка напоминаний о делах."""
    async with aiosqlite.connect(db.DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute("SELECT DISTINCT user_id FROM todo_list") as cursor:
            users = await cursor.fetchall()

        tomorrow = date.today() + timedelta(days=1)

        for user in users:
            user_id = user['user_id']
            todos = await db.get_todos_for_reminder(user_id, tomorrow)

            if todos:
                message = "⏰ Напоминание о делах на завтра:\n\n"
                for todo in todos:
                    message += f"• {todo['task']}\n"
                    await db.mark_todo_reminded(user_id, todo['id'])

                try:
                    send_message(vk, user_id, message)
                except Exception:
                    pass


async def reminder_scheduler(vk):
    """Планировщик напоминаний (каждый день в 9:00)."""
    last_sent_date = None

    while True:
        now = datetime.now()
        current_date = now.date()

        if now.hour == 9 and now.minute == 0:
            if last_sent_date != current_date:
                await send_reminders(vk)
                last_sent_date = current_date

        if now.hour == 0 and now.minute == 1:
            last_sent_date = None

        await asyncio.sleep(60)


async def weather_scheduler(vk):
    """Планировщик погоды."""
    last_sent = {}
    city_timezones = {}

    while True:
        now_utc = datetime.now(UTC)

        async with aiosqlite.connect(db.DB_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute(
                "SELECT user_id, weather_city, weather_daily, weather_rain, weather_time FROM category_settings WHERE weather_city != '' AND weather_city IS NOT NULL"
            ) as cursor:
                users = await cursor.fetchall()

        for user in users:
            user_id = user['user_id']
            city = user['weather_city']
            user_time = user['weather_time'] if user['weather_time'] else '06:00'

            weather_daily = bool(user['weather_daily']) if user['weather_daily'] is not None else False
            weather_rain = bool(user['weather_rain']) if user['weather_rain'] is not None else False

            tz_offset = city_timezones.get(city)
            if tz_offset is None:
                weather_data = await get_weather(city)
                if weather_data.get("success"):
                    tz_offset = weather_data.get("timezone", 0)
                    city_timezones[city] = tz_offset
                else:
                    continue

            user_local_time = now_utc + timedelta(seconds=tz_offset)
            user_time_str = user_local_time.strftime('%H:%M')
            user_date = user_local_time.date()

            if user_time_str == user_time:
                if user_id not in last_sent or last_sent[user_id] != user_date:
                    try:
                        if weather_daily:
                            await send_weather_report(vk, user_id, city)
                        last_sent[user_id] = user_date
                    except Exception:
                        pass

        if now_utc.hour == 0 and now_utc.minute == 1:
            last_sent.clear()

        await asyncio.sleep(60)


# ============================================================
# === ОСНОВНОЙ ЗАПУСК
# ============================================================

def main():
    """Основная функция запуска бота."""
    import os
    import sys

    # Инициализация БД
    run_async(db.init_db())

    # Авторизация VK
    vk_session = VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    # Long Poll (для VK API нужен положительный ID группы)
    group_id_positive = str(VK_GROUP_ID).lstrip('-')  # Убираем минус
    longpoll = VkBotLongPoll(vk_session, int(group_id_positive))

    print(f"VKAssistant запущен (версия {BOT_VERSION})...")

    # Запуск планировщиков (каждый в своём потоке со своим loop)
    def run_scheduler(coro):
        scheduler_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(scheduler_loop)
        scheduler_loop.run_until_complete(coro)

    import threading
    threading.Thread(target=lambda: run_scheduler(reminder_scheduler(vk)), daemon=True).start()
    threading.Thread(target=lambda: run_scheduler(weather_scheduler(vk)), daemon=True).start()

    # Основной цикл обработки событий
    for event in longpoll.listen():
        try:
            if event.type == VkBotEventType.MESSAGE_NEW:
                user_id = event.obj.message['from_id']
                text = event.obj.message['text'].strip()

                # Обработка команд
                if text.startswith('/'):
                    command = text.split()[0].lower()
                    if command == '/start':
                        handle_start(vk, user_id)
                    elif command == '/help':
                        handle_help(vk, user_id)
                    elif command == '/version':
                        handle_version(vk, user_id)
                    elif command == '/admin':
                        handle_admin(vk, user_id)
                    elif command == '/update':
                        handle_update(vk, user_id)
                    elif command == '/categories':
                        handle_categories(vk, user_id)
                    elif command == '/cancel':
                        handle_cancel(vk, user_id)
                    elif command == '/done':
                        handle_done(vk, user_id)
                    else:
                        send_message(vk, user_id, "❌ Неизвестная команда. Напишите /help для справки.")
                else:
                    handle_text_message(vk, user_id, text)

            elif event.type == VkBotEventType.MESSAGE_EVENT:
                # Отправляем ответ на callback (обязательно для VK)
                try:
                    event_id = event.obj.event_id
                    user_id = event.obj.user_id
                    
                    vk.messages.sendMessageEventAnswer(
                        event_id=event_id,
                        user_id=user_id,
                        peer_id=event.obj.peer_id,
                        event_data=json.dumps({"type": "show_snackbar", "text": "Обработка..."})
                    )
                except Exception as e:
                    print(f"Ошибка отправки callback ответа: {e}")
                
                try:
                    handle_callback(vk, event)
                except Exception as e:
                    print(f"[ERROR] handle_callback: {e}")
                    import traceback
                    traceback.print_exc()
            
            elif event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                pass  # Игнорируем события набора текста

        except Exception as e:
            print(f"Ошибка обработки события: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
