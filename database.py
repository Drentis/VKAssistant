"""
Модуль работы с базой данных SQLite для TelegramAssistant.

Этот модуль предоставляет функции для управления всеми аспектами бота:
- Список покупок (shopping_list)
- Список дел (todo_list)
- Учебные задачи (study_list)
- Идеи (ideas_list)
- Рецепты (recipes, recipe_ingredients)
- Настройки пользователя (category_settings)

База данных: notebook.db (SQLite)
"""

import aiosqlite
from datetime import date
from typing import Optional

# Путь к файлу базы данных (в той же директории, где и скрипт)
DB_PATH = "notebook.db"


async def init_db():
    """
    Инициализация базы данных.

    Создаёт все необходимые таблицы, если они не существуют.
    Также добавляет новые поля в существующие таблицы (для совместимости).

    Таблицы:
    - shopping_list: товары для покупок с категориями
    - category_settings: настройки пользователя (названия магазинов, триггеры, видимость кнопок)
    - todo_list: задачи с датами выполнения и напоминаниями
    - study_list: учебные задачи
    - ideas_list: быстрые заметки/идеи
    - recipes: рецепты с описаниями
    - recipe_ingredients: ингредиенты для рецептов

    Вызывается один раз при запуске бота.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица покупок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shopping_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                category TEXT NOT NULL,
                taken INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Добавляем поле taken, если его нет (для существующих баз)
        try:
            await db.execute("ALTER TABLE shopping_list ADD COLUMN taken INTEGER DEFAULT 0")
        except Exception:
            pass  # Поле уже существует

        # Таблица настроек категорий
        await db.execute("""
            CREATE TABLE IF NOT EXISTS category_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                magnit_name TEXT DEFAULT 'Магнит',
                magnit_short TEXT DEFAULT 'м',
                magnit_desc TEXT DEFAULT 'Продукты',
                fixprice_name TEXT DEFAULT 'Фикспрайс',
                fixprice_short TEXT DEFAULT 'ф',
                fixprice_desc TEXT DEFAULT 'Бытовое',
                other_name TEXT DEFAULT 'Другое',
                other_short TEXT DEFAULT 'д',
                other_desc TEXT DEFAULT 'Другое',
                buy_trigger TEXT DEFAULT 'купить',
                todo_trigger TEXT DEFAULT 'сделать',
                study_trigger TEXT DEFAULT 'учёба'
            )
        """)

        # Добавляем новые поля, если их нет (для существующих баз)
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN magnit_desc TEXT DEFAULT 'Продукты'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN fixprice_desc TEXT DEFAULT 'Бытовое'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN other_desc TEXT DEFAULT 'Другое'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN buy_trigger TEXT DEFAULT 'купить'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN todo_trigger TEXT DEFAULT 'сделать'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN study_trigger TEXT DEFAULT 'учёба'")
        except Exception:
            pass

        # Таблица дел
        await db.execute("""
            CREATE TABLE IF NOT EXISTS todo_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                due_date DATE,
                reminded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Таблица учёбы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS study_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица идей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ideas_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                idea TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Добавляем поле ideas_trigger в настройки
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN ideas_trigger TEXT DEFAULT 'идея'")
        except Exception:
            pass

        # Таблица рецептов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица ингредиентов рецептов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                ingredient TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
            )
        """)

        # Таблица пользовательских категорий
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                short TEXT NOT NULL,
                description TEXT DEFAULT '',
                keywords TEXT DEFAULT '',
                icon TEXT DEFAULT '📦',
                color TEXT DEFAULT 'default',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
        """)

        # Добавляем поле recipes_trigger в настройки
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN recipes_trigger TEXT DEFAULT 'рецепт'")
        except Exception:
            pass

        # Добавляем поля visibility для кнопок меню (по умолчанию все включены)
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN visibility_todo INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN visibility_study INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN visibility_ideas INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN visibility_recipes INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN visibility_shopping INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN visibility_info INTEGER DEFAULT 1")
        except Exception:
            pass

        # Добавляем поля для погоды
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN weather_city TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN weather_daily INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN weather_rain INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN weather_button INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE category_settings ADD COLUMN weather_time TEXT DEFAULT '06:00'")
        except Exception:
            pass

        await db.commit()


# ============================================================
# === СПИСОК ПОКУПОК (Shopping List)
# ============================================================

async def add_shopping_item(user_id: int, item: str, category: str) -> tuple[bool, str]:
    """
    Добавить товар в список покупок.

    Args:
        user_id: ID пользователя в Telegram
        item: Название товара (например, "Молоко")
        category: Категория магазина ("magnit", "fixprice", "other")

    Returns:
        tuple[bool, str]: (True, "added") если успешно,
                          (False, "already_exists") если товар уже есть

    Примечание:
        Товары проверяются на дубликаты в рамках одной категории.
        Один и тот же товар может быть в разных категориях.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Проверяем, есть ли уже такой товар в этой категории
        async with db.execute(
            "SELECT id FROM shopping_list WHERE user_id = ? AND item = ? AND category = ?",
            (user_id, item, category)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            return False, "already_exists"

        await db.execute(
            "INSERT INTO shopping_list (user_id, item, category) VALUES (?, ?, ?)",
            (user_id, item, category)
        )
        await db.commit()
        return True, "added"


async def get_shopping_items(user_id: int, category: Optional[str] = None):
    """
    Получить товары из списка покупок.

    Args:
        user_id: ID пользователя в Telegram
        category: Фильтр по категории (None = все категории)

    Returns:
        Список товаров (dict) с полями: id, user_id, item, category, taken, created_at

    Примечание:
        Товары сортируются по дате добавления (новые первыми).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category:
            async with db.execute(
                "SELECT * FROM shopping_list WHERE user_id = ? AND category = ? ORDER BY created_at DESC",
                (user_id, category)
            ) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM shopping_list WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ) as cursor:
                return await cursor.fetchall()


async def delete_shopping_item(user_id: int, item_id: int):
    """
    Удалить товар из списка покупок.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID товара в базе данных

    Примечание:
        Удаление происходит только если товар принадлежит пользователю.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM shopping_list WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        await db.commit()


async def toggle_shopping_item_taken(user_id: int, item_id: int) -> bool:
    """
    Переключить статус "взято" у товара.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID товара в базе данных

    Returns:
        bool: Новый статус taken (True = взято, False = не взято)

    Примечание:
        Используется для отметки товаров, которые пользователь уже купил.
        Взятое скрывается из списка при просмотре.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Получаем текущий статус
        async with db.execute(
            "SELECT taken FROM shopping_list WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return False

        new_taken = 0 if row['taken'] else 1
        await db.execute(
            "UPDATE shopping_list SET taken = ? WHERE id = ? AND user_id = ?",
            (new_taken, item_id, user_id)
        )
        await db.commit()
        return new_taken == 1


async def clear_shopping_list(user_id: int, category: Optional[str] = None):
    """
    Очистить список покупок (удалить все товары).

    Args:
        user_id: ID пользователя в Telegram
        category: Фильтр по категории (None = очистить все категории)

    Примечание:
        Если указана категория, удаляются только товары из неё.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        if category:
            await db.execute(
                "DELETE FROM shopping_list WHERE user_id = ? AND category = ?",
                (user_id, category)
            )
        else:
            await db.execute(
                "DELETE FROM shopping_list WHERE user_id = ?",
                (user_id,)
            )
        await db.commit()


# ============================================================
# === СПИСОК ДЕЛ (Todo List)
# ============================================================

async def add_todo_item(user_id: int, task: str, due_date: Optional[date] = None) -> tuple[bool, str]:
    """
    Добавить задачу в список дел.

    Args:
        user_id: ID пользователя в Telegram
        task: Текст задачи (например, "Купить хлеб")
        due_date: Срок выполнения (date или None)

    Returns:
        tuple[bool, str]: (True, "added") если успешно,
                          (False, "already_exists") если задача уже есть

    Примечание:
        Задачи проверяются на дубликаты без учёта даты.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Проверяем, есть ли уже такая задача (без учёта даты)
        async with db.execute(
            "SELECT id FROM todo_list WHERE user_id = ? AND task = ?",
            (user_id, task)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            return False, "already_exists"

        await db.execute(
            "INSERT INTO todo_list (user_id, task, due_date) VALUES (?, ?, ?)",
            (user_id, task, due_date.isoformat() if due_date else None)
        )
        await db.commit()
        return True, "added"


async def get_todo_items(user_id: int):
    """
    Получить все задачи из списка дел.

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        Список задач (dict) с полями: id, user_id, task, due_date, reminded, created_at

    Примечание:
        Задачи сортируются: сначала с датой (по возрастанию), затем без даты.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM todo_list WHERE user_id = ? ORDER BY due_date ASC, created_at DESC",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def delete_todo_item(user_id: int, item_id: int):
    """
    Удалить задачу из списка дел.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID задачи в базе данных
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM todo_list WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        await db.commit()


async def clear_todo_list(user_id: int):
    """
    Очистить список дел (удалить все задачи).

    Args:
        user_id: ID пользователя в Telegram
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM todo_list WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def update_todo_item(user_id: int, item_id: int, task: str, due_date: Optional[date] = None):
    """
    Обновить задачу в списке дел.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID задачи в базе данных
        task: Новый текст задачи
        due_date: Новый срок выполнения (date или None)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE todo_list SET task = ?, due_date = ? WHERE id = ? AND user_id = ?",
            (task, due_date.isoformat() if due_date else None, item_id, user_id)
        )
        await db.commit()


async def update_study_item(user_id: int, item_id: int, task: str):
    """
    Обновить задачу в списке учёбы.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID задачи в базе данных
        task: Новый текст учебной задачи
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE study_list SET task = ? WHERE id = ? AND user_id = ?",
            (task, item_id, user_id)
        )
        await db.commit()


async def update_idea(user_id: int, item_id: int, idea: str):
    """
    Обновить идею в списке идей.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID идеи в базе данных
        idea: Новый текст идеи
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE ideas_list SET idea = ? WHERE id = ? AND user_id = ?",
            (idea, item_id, user_id)
        )
        await db.commit()


async def get_todos_for_reminder(user_id: int, target_date: date):
    """
    Получить задачи для напоминания на указанную дату.

    Args:
        user_id: ID пользователя в Telegram
        target_date: Дата, на которую нужно найти задачи

    Returns:
        Список задач, о которых ещё не было напоминания

    Примечание:
        Возвращает только задачи с reminded=0 (о которых ещё не напоминали).
        Используется планировщиком напоминаний.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM todo_list
               WHERE user_id = ? AND due_date = ? AND reminded = 0""",
            (user_id, target_date.isoformat())
        ) as cursor:
            return await cursor.fetchall()


async def mark_todo_reminded(user_id: int, item_id: int):
    """
    Отметить задачу как напомненную.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID задачи в базе данных

    Примечание:
        Устанавливает reminded=1, чтобы не напоминать повторно.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE todo_list SET reminded = 1 WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        await db.commit()


# ============================================================
# === УЧЁБА (Study List)
# ============================================================

async def add_study_item(user_id: int, task: str) -> tuple[bool, str]:
    """
    Добавить задачу в список учёбы.

    Args:
        user_id: ID пользователя в Telegram
        task: Текст учебной задачи

    Returns:
        tuple[bool, str]: (True, "added") если успешно,
                          (False, "already_exists") если задача уже есть
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Проверяем, есть ли уже такая задача
        async with db.execute(
            "SELECT id FROM study_list WHERE user_id = ? AND task = ?",
            (user_id, task)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            return False, "already_exists"

        await db.execute(
            "INSERT INTO study_list (user_id, task) VALUES (?, ?)",
            (user_id, task)
        )
        await db.commit()
        return True, "added"


async def get_study_items(user_id: int):
    """
    Получить все задачи из списка учёбы.

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        Список задач (dict) с полями: id, user_id, task, created_at
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM study_list WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def delete_study_item(user_id: int, item_id: int):
    """
    Удалить задачу из списка учёбы.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID задачи в базе данных
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM study_list WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        await db.commit()


async def clear_study_list(user_id: int):
    """
    Очистить список учёбы (удалить все задачи).

    Args:
        user_id: ID пользователя в Telegram
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM study_list WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


# ============================================================
# === ИДЕИ (Ideas List)
# ============================================================

async def add_idea(user_id: int, idea: str) -> tuple[bool, str]:
    """
    Добавить идею в список идей.

    Args:
        user_id: ID пользователя в Telegram
        idea: Текст идеи

    Returns:
        tuple[bool, str]: (True, "added") если успешно,
                          (False, "already_exists") если идея уже есть
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Проверяем, есть ли уже такая идея
        async with db.execute(
            "SELECT id FROM ideas_list WHERE user_id = ? AND idea = ?",
            (user_id, idea)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            return False, "already_exists"

        await db.execute(
            "INSERT INTO ideas_list (user_id, idea) VALUES (?, ?)",
            (user_id, idea)
        )
        await db.commit()
        return True, "added"


async def get_ideas(user_id: int):
    """
    Получить все идеи пользователя.

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        Список идей (dict) с полями: id, user_id, idea, created_at
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ideas_list WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def delete_idea(user_id: int, item_id: int):
    """
    Удалить идею из списка.

    Args:
        user_id: ID пользователя в Telegram
        item_id: ID идеи в базе данных
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM ideas_list WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        await db.commit()


async def clear_ideas_list(user_id: int):
    """
    Очистить список идей (удалить все идеи).

    Args:
        user_id: ID пользователя в Telegram
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM ideas_list WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


# ============================================================
# === РЕЦЕПТЫ (Recipes)
# ============================================================

async def add_recipe(user_id: int, name: str, description: str = None) -> tuple[int, str]:
    """
    Добавить новый рецепт.

    Args:
        user_id: ID пользователя в Telegram
        name: Название рецепта
        description: Описание/инструкция приготовления (необязательно)

    Returns:
        tuple[int, str]: (id рецепта, "added") если успешно,
                         (0, "already_exists") если рецепт уже есть

    Примечание:
        Возвращает ID созданного рецепта для последующего добавления ингредиентов.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли уже такой рецепт
        async with db.execute(
            "SELECT id FROM recipes WHERE user_id = ? AND name = ?",
            (user_id, name)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            return 0, "already_exists"

        cursor = await db.execute(
            "INSERT INTO recipes (user_id, name, description) VALUES (?, ?, ?)",
            (user_id, name, description)
        )
        recipe_id = cursor.lastrowid
        await db.commit()
        return recipe_id, "added"


async def add_recipe_ingredient(recipe_id: int, ingredient: str) -> bool:
    """
    Добавить ингредиент к рецепту.

    Args:
        recipe_id: ID рецепта в базе данных
        ingredient: Текст ингредиента (например, "Молоко 500мл")

    Returns:
        bool: True если добавлен, False если уже существовал

    Примечание:
        Ингредиенты проверяются на дубликаты в рамках одного рецепта.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли уже такой ингредиент
        async with db.execute(
            "SELECT id FROM recipe_ingredients WHERE recipe_id = ? AND ingredient = ?",
            (recipe_id, ingredient)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            return False

        await db.execute(
            "INSERT INTO recipe_ingredients (recipe_id, ingredient) VALUES (?, ?)",
            (recipe_id, ingredient)
        )
        await db.commit()
        return True


async def get_recipes(user_id: int):
    """
    Получить все рецепты пользователя.

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        Список рецептов (dict) с полями: id, user_id, name, description, created_at
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM recipes WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def get_recipe(user_id: int, recipe_id: int):
    """
    Получить рецепт по ID.

    Args:
        user_id: ID пользователя в Telegram
        recipe_id: ID рецепта в базе данных

    Returns:
        dict с полями рецепта или None если не найден
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM recipes WHERE id = ? AND user_id = ?",
            (recipe_id, user_id)
        ) as cursor:
            return await cursor.fetchone()


async def get_recipe_ingredients(recipe_id: int):
    """
    Получить все ингредиенты рецепта.

    Args:
        recipe_id: ID рецепта в базе данных

    Returns:
        Список ингредиентов (dict) с полями: id, recipe_id, ingredient
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM recipe_ingredients WHERE recipe_id = ? ORDER BY id",
            (recipe_id,)
        ) as cursor:
            return await cursor.fetchall()


async def delete_recipe(user_id: int, recipe_id: int):
    """
    Удалить рецепт и все его ингредиенты.

    Args:
        user_id: ID пользователя в Telegram
        recipe_id: ID рецепта в базе данных

    Примечание:
        Сначала удаляются ингредиенты из recipe_ingredients, затем сам рецепт.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Сначала удаляем ингредиенты
        await db.execute(
            "DELETE FROM recipe_ingredients WHERE recipe_id = ?",
            (recipe_id,)
        )
        # Затем удаляем рецепт
        await db.execute(
            "DELETE FROM recipes WHERE id = ? AND user_id = ?",
            (recipe_id, user_id)
        )
        await db.commit()


async def clear_recipes_list(user_id: int):
    """
    Очистить все рецепты пользователя.

    Args:
        user_id: ID пользователя в Telegram

    Примечание:
        Удаляет все рецепты и их ингредиенты.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем все рецепты пользователя
        async with db.execute("SELECT id FROM recipes WHERE user_id = ?", (user_id,)) as cursor:
            recipes = await cursor.fetchall()

        # Удаляем ингредиенты для всех рецептов
        for recipe in recipes:
            await db.execute(
                "DELETE FROM recipe_ingredients WHERE recipe_id = ?",
                (recipe['id'],)
            )

        # Удаляем все рецепты
        await db.execute("DELETE FROM recipes WHERE user_id = ?", (user_id,))
        await db.commit()


# ============================================================
# === НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ (Category Settings)
# ============================================================

async def get_category_settings(user_id: int) -> dict:
    """
    Получить настройки категорий пользователя.

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        dict с настройками:
        - magnit_name, magnit_short, magnit_desc: название, сокращение, описание Магнита
        - fixprice_name, fixprice_short, fixprice_desc: аналогично для Фикспрайс
        - other_name, other_short, other_desc: аналогично для Другое
        - buy_trigger, todo_trigger, study_trigger, ideas_trigger, recipes_trigger: триггерные слова
        - visibility_*: видимость кнопок меню (1=включено, 0=выключено)
        - weather_city, weather_daily, weather_rain, weather_button, weather_time: настройки погоды

    Примечание:
        Если настроек нет, возвращает значения по умолчанию.
        Обеспечивает обратную совместимость со старыми полями.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM category_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return {
                'magnit_name': row['magnit_name'],
                'magnit_short': row['magnit_short'],
                'magnit_desc': row['magnit_desc'] if 'magnit_desc' in row.keys() else 'Продукты',
                'fixprice_name': row['fixprice_name'],
                'fixprice_short': row['fixprice_short'],
                'fixprice_desc': row['fixprice_desc'] if 'fixprice_desc' in row.keys() else 'Бытовое',
                'other_name': row['other_name'],
                'other_short': row['other_short'],
                'other_desc': row['other_desc'] if 'other_desc' in row.keys() else 'Другое',
                'buy_trigger': row['buy_trigger'] if 'buy_trigger' in row.keys() else 'купить',
                'todo_trigger': row['todo_trigger'] if 'todo_trigger' in row.keys() else 'сделать',
                'study_trigger': row['study_trigger'] if 'study_trigger' in row.keys() else 'учёба',
                'ideas_trigger': row['ideas_trigger'] if 'ideas_trigger' in row.keys() else 'идея',
                'recipes_trigger': row['recipes_trigger'] if 'recipes_trigger' in row.keys() else 'рецепт',
                'visibility_todo': row['visibility_todo'] if 'visibility_todo' in row.keys() else 1,
                'visibility_study': row['visibility_study'] if 'visibility_study' in row.keys() else 1,
                'visibility_ideas': row['visibility_ideas'] if 'visibility_ideas' in row.keys() else 1,
                'visibility_recipes': row['visibility_recipes'] if 'visibility_recipes' in row.keys() else 1,
                'visibility_shopping': row['visibility_shopping'] if 'visibility_shopping' in row.keys() else 1,
                'visibility_info': row['visibility_info'] if 'visibility_info' in row.keys() else 1,
                'weather_city': row['weather_city'] if 'weather_city' in row.keys() else '',
                'weather_daily': row['weather_daily'] if 'weather_daily' in row.keys() else 0,
                'weather_rain': row['weather_rain'] if 'weather_rain' in row.keys() else 0,
                'weather_button': row['weather_button'] if 'weather_button' in row.keys() else 1,
                'weather_time': row['weather_time'] if 'weather_time' in row.keys() else '06:00'
            }
        else:
            # Настройки по умолчанию
            return {
                'magnit_name': 'Магнит',
                'magnit_short': 'м',
                'magnit_desc': 'Продукты',
                'fixprice_name': 'Фикспрайс',
                'fixprice_short': 'ф',
                'fixprice_desc': 'Бытовое',
                'other_name': 'Другое',
                'other_short': 'д',
                'other_desc': 'Другое',
                'buy_trigger': 'купить',
                'todo_trigger': 'сделать',
                'study_trigger': 'учёба',
                'ideas_trigger': 'идея',
                'recipes_trigger': 'рецепт',
                'visibility_todo': 1,
                'visibility_study': 1,
                'visibility_ideas': 1,
                'visibility_recipes': 1,
                'visibility_shopping': 1,
                'visibility_info': 1,
                'weather_city': '',
                'weather_daily': 0,
                'weather_rain': 0,
                'weather_button': 1,
                'weather_time': '06:00'
            }


async def update_category_settings(user_id: int, **kwargs):
    """
    Обновить настройки категорий пользователя.

    Args:
        user_id: ID пользователя в Telegram
        **kwargs: Произвольные параметры для обновления, например:
                  magnit_name='Перекрёсток', weather_city='Москва', visibility_todo=0

    Примечание:
        Если настроек нет, создаёт новые с указанными параметрами и дефолтными значениями.
        Обновляет только переданные параметры, остальные остаются без изменений.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли уже настройки
        async with db.execute(
            "SELECT id FROM category_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            # Обновляем существующие
            sets = []
            values = []
            for key, value in kwargs.items():
                sets.append(f"{key} = ?")
                values.append(value)
            values.append(user_id)
            await db.execute(
                f"UPDATE category_settings SET {', '.join(sets)} WHERE user_id = ?",
                values
            )
        else:
            # Создаём новые
            await db.execute(
                """INSERT INTO category_settings
                   (user_id, magnit_name, magnit_short, magnit_desc, fixprice_name, fixprice_short, fixprice_desc, other_name, other_short, other_desc, buy_trigger, todo_trigger, study_trigger, ideas_trigger, recipes_trigger, visibility_todo, visibility_study, visibility_ideas, visibility_recipes, visibility_shopping, visibility_info, weather_city, weather_daily, weather_rain, weather_button, weather_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id,
                 kwargs.get('magnit_name', 'Магнит'),
                 kwargs.get('magnit_short', 'м'),
                 kwargs.get('magnit_desc', 'Продукты'),
                 kwargs.get('fixprice_name', 'Фикспрайс'),
                 kwargs.get('fixprice_short', 'ф'),
                 kwargs.get('fixprice_desc', 'Бытовое'),
                 kwargs.get('other_name', 'Другое'),
                 kwargs.get('other_short', 'д'),
                 kwargs.get('other_desc', 'Другое'),
                 kwargs.get('buy_trigger', 'купить'),
                 kwargs.get('todo_trigger', 'сделать'),
                 kwargs.get('study_trigger', 'учёба'),
                 kwargs.get('ideas_trigger', 'идея'),
                 kwargs.get('recipes_trigger', 'рецепт'),
                 kwargs.get('visibility_todo', 1),
                 kwargs.get('visibility_study', 1),
                 kwargs.get('visibility_ideas', 1),
                 kwargs.get('visibility_recipes', 1),
                 kwargs.get('visibility_shopping', 1),
                 kwargs.get('visibility_info', 1),
                 kwargs.get('weather_city', ''),
                 kwargs.get('weather_daily', 0),
                 kwargs.get('weather_rain', 0),
                 kwargs.get('weather_button', 1),
                 kwargs.get('weather_time', '06:00'))
            )
        await db.commit()


# ============================================================
# === СБРОС ПРОФИЛЯ (Reset Profile)
# ============================================================

async def reset_user_profile(user_id: int):
    """
    Полный сброс профиля пользователя к заводским настройкам.

    Args:
        user_id: ID пользователя в Telegram

    Удаляет:
        - Все товары из списка покупок
        - Все задачи из списка дел
        - Все учебные задачи
        - Все идеи
        - Все рецепты с ингредиентами
        - Сбрасывает настройки пользователя к значениям по умолчанию
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Удаляем все данные пользователя
        await db.execute("DELETE FROM shopping_list WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM todo_list WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM study_list WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM ideas_list WHERE user_id = ?", (user_id,))
        
        # Удаляем ингредиенты рецептов (сначала)
        await db.execute("""
            DELETE FROM recipe_ingredients 
            WHERE recipe_id IN (SELECT id FROM recipes WHERE user_id = ?)
        """, (user_id,))
        
        # Удаляем рецепты
        await db.execute("DELETE FROM recipes WHERE user_id = ?", (user_id,))
        
        # Сбрасываем настройки к значениям по умолчанию
        await db.execute("""
            UPDATE category_settings SET
                magnit_name = 'Магнит',
                magnit_short = 'м',
                magnit_desc = 'Продукты',
                fixprice_name = 'Фикспрайс',
                fixprice_short = 'ф',
                fixprice_desc = 'Бытовое',
                other_name = 'Другое',
                other_short = 'д',
                other_desc = 'Другое',
                buy_trigger = 'купить',
                todo_trigger = 'сделать',
                study_trigger = 'учёба',
                ideas_trigger = 'идея',
                recipes_trigger = 'рецепт',
                visibility_todo = 1,
                visibility_study = 1,
                visibility_ideas = 1,
                visibility_recipes = 1,
                visibility_shopping = 1,
                visibility_info = 1,
                weather_city = '',
                weather_daily = 0,
                weather_rain = 0,
                weather_button = 1,
                weather_time = '06:00'
            WHERE user_id = ?
        """, (user_id,))

        await db.commit()


# ============================================================
# === СТАТИСТИКА (Admin Panel)
# ============================================================

async def get_global_stats() -> dict:
    """
    Получить общую статистику по всем пользователям.

    Returns:
        dict: Статистика с полями:
            - total_users: Количество уникальных пользователей
            - total_shopping: Всего товаров в покупках
            - total_todo: Всего задач в делах
            - total_study: Всего учебных задач
            - total_ideas: Всего идей
            - total_recipes: Всего рецептов
            - active_users_today: Активных пользователей за сегодня
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Количество уникальных пользователей
        async with db.execute("SELECT COUNT(DISTINCT user_id) as count FROM shopping_list") as cursor:
            total_users = (await cursor.fetchone())['count']

        # Всего товаров в покупках
        async with db.execute("SELECT COUNT(*) as count FROM shopping_list") as cursor:
            total_shopping = (await cursor.fetchone())['count']

        # Всего задач в делах
        async with db.execute("SELECT COUNT(*) as count FROM todo_list") as cursor:
            total_todo = (await cursor.fetchone())['count']

        # Всего учебных задач
        async with db.execute("SELECT COUNT(*) as count FROM study_list") as cursor:
            total_study = (await cursor.fetchone())['count']

        # Всего идей
        async with db.execute("SELECT COUNT(*) as count FROM ideas_list") as cursor:
            total_ideas = (await cursor.fetchone())['count']

        # Всего рецептов
        async with db.execute("SELECT COUNT(*) as count FROM recipes") as cursor:
            total_recipes = (await cursor.fetchone())['count']

        return {
            "total_users": total_users,
            "total_shopping": total_shopping,
            "total_todo": total_todo,
            "total_study": total_study,
            "total_ideas": total_ideas,
            "total_recipes": total_recipes,
        }


async def get_user_stats(user_id: int) -> dict:
    """
    Получить статистику по конкретному пользователю.

    Args:
        user_id: ID пользователя

    Returns:
        dict: Статистика пользователя
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Количество товаров в покупках
        async with db.execute("SELECT COUNT(*) as count FROM shopping_list WHERE user_id = ?", (user_id,)) as cursor:
            shopping_count = (await cursor.fetchone())['count']

        # Количество задач в делах
        async with db.execute("SELECT COUNT(*) as count FROM todo_list WHERE user_id = ?", (user_id,)) as cursor:
            todo_count = (await cursor.fetchone())['count']

        # Количество учебных задач
        async with db.execute("SELECT COUNT(*) as count FROM study_list WHERE user_id = ?", (user_id,)) as cursor:
            study_count = (await cursor.fetchone())['count']

        # Количество идей
        async with db.execute("SELECT COUNT(*) as count FROM ideas_list WHERE user_id = ?", (user_id,)) as cursor:
            ideas_count = (await cursor.fetchone())['count']

        # Количество рецептов
        async with db.execute("SELECT COUNT(*) as count FROM recipes WHERE user_id = ?", (user_id,)) as cursor:
            recipes_count = (await cursor.fetchone())['count']

        return {
            "shopping_count": shopping_count,
            "todo_count": todo_count,
            "study_count": study_count,
            "ideas_count": ideas_count,
            "recipes_count": recipes_count,
        }


# ============================================================
# === ПОЛЬЗОВАТЕЛЬСКИЕ КАТЕГОРИИ (Custom Categories)
# ============================================================

async def add_custom_category(user_id: int, name: str, short: str, description: str = '', keywords: str = '', icon: str = '📦', color: str = 'default') -> tuple[bool, str]:
    """
    Добавить пользовательскую категорию.

    Args:
        user_id: ID пользователя
        name: Название категории (например, "Пятёрочка")
        short: Сокращение (например, "п")
        description: Описание категории
        keywords: Ключевые слова для автоклассификации (через запятую)
        icon: Эмодзи-иконка
        color: Цвет кнопки

    Returns:
        tuple[bool, str]: (True, "added") если успешно, (False, "already_exists") если уже есть
    """
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO custom_categories (user_id, name, short, description, keywords, icon, color) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, short, description, keywords, icon, color)
            )
            await db.commit()
            return True, "added"
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                return False, "already_exists"
            raise


async def get_custom_categories(user_id: int) -> list:
    """
    Получить все пользовательские категории.

    Args:
        user_id: ID пользователя

    Returns:
        list: Список категорий (dict) с полями: id, name, short, description, keywords, icon, color
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM custom_categories WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def get_custom_category(user_id: int, category_id: int):
    """
    Получить пользовательскую категорию по ID.

    Args:
        user_id: ID пользователя
        category_id: ID категории

    Returns:
        dict или None если не найдена
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM custom_categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        ) as cursor:
            return await cursor.fetchone()


async def update_custom_category(user_id: int, category_id: int, **kwargs) -> bool:
    """
    Обновить пользовательскую категорию.

    Args:
        user_id: ID пользователя
        category_id: ID категории
        **kwargs: Поля для обновления (name, short, description, keywords, icon, color)

    Returns:
        bool: True если обновлено, False если не найдено
    """
    if not kwargs:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [category_id, user_id]
        
        await db.execute(
            f"UPDATE custom_categories SET {set_clause} WHERE id = ? AND user_id = ?",
            values
        )
        await db.commit()
        return True


async def delete_custom_category(user_id: int, category_id: int) -> bool:
    """
    Удалить пользовательскую категорию.

    Args:
        user_id: ID пользователя
        category_id: ID категории

    Returns:
        bool: True если удалено, False если не найдено
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM custom_categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
        return db.total_changes > 0
