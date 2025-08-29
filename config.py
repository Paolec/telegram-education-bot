import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID'))
    DB_NAME = os.getenv('DB_NAME', 'orders.db')
    MAX_ACTIVE_ORDERS = int(os.getenv('MAX_ACTIVE_ORDERS', 3))
    MIN_BUDGET = int(os.getenv('MIN_BUDGET', 200))
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 20971520))
    BASE_UPLOAD_FOLDER = "uploads"
    COMPLETED_FOLDER = "completed_work"
    MAX_MESSAGE_LENGTH = 4096
    MAX_FILES_PER_MESSAGE = 10

    # Статусы заказов
    ORDER_STATUSES = {
        'new': '🔍 Поиск исполнителя',
        'in_progress': '🛠 На выполнении',
        'completed': '✅ Выполнен',
        'cancelled': '❌ Отменен'
    }

    # Системы проверки антиплагиата
    PLAGIARISM_SYSTEMS = {
        "anti_ru": {
            "name": "1️⃣ Антиплагиат.РУ",
            "description": "Бесплатная проверка по открытым источникам",
            "emoji": "🆓",
            "requirements": "Без дополнительных требований"
        },
        "anti_vuz": {
            "name": "2️⃣ Антиплагиат.ВУЗ",
            "description": "Проверка по закрытой базе ВУЗов",
            "emoji": "🎓",
            "requirements": "Предоставление доступа к Антиплагиат.ВУЗ обязательно!"
        },
        "etxt": {
            "name": "3️⃣ eTXT",
            "description": "Проверка через сервис eTXT",
            "emoji": "🔍",
            "requirements": "Отчет в формате PDF"
        }
    }

    # Категории для выбора
    DISCIPLINES = [
        ("math", "🧮 Математические дисциплины"),
        ("science", "🔬 Естественные дисциплины"),
        ("tech", "⚙️ Технические дисциплины"),
        ("programming", "💻 Программирование"),
        ("humanities", "📚 Гуманитарные дисциплины"),
        ("economics", "📊 Экономические дисциплины"),
        ("law", "⚖️ Правовые дисциплины"),
        ("languages", "🌍 Иностранные языки"),
        ("text", "📝 Работа с текстом")
    ]

    # Универсальные типы работ для всех дисциплин
    WORK_TYPES = [
        ("problem", "📝 Задача"),
        ("control", "📄 Контрольная работа"),
        ("course", "📚 Курсовая работа"),
        ("lab", "🧪 Лабораторная работа"),
        ("diploma", "🎓 Дипломная работа"),
        ("referat", "📑 Реферат"),
        ("practice", "🏢 Отчет по практике"),
        ("test", "✅ Тест"),
        ("drawing", "📐 Чертеж"),
        ("online", "💻 Онлайн помощь"),
        ("essay", "✍️ Эссе"),
        ("translation", "🌐 Перевод"),
        ("vkr", "🎓 ВКР (Выпускная квалификационная работа)"),
        ("other", "❓ Другое (указать в описании)")
    ]

    # Разрешенные типы файлов
    ALLOWED_FILE_TYPES = [
        'image/jpeg', 'image/png', 'image/jpg',
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/zip', 'application/x-rar-compressed',
        'application/x-7z-compressed', 'text/plain'
    ]