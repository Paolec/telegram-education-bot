import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect(Config.DB_NAME)
        c = conn.cursor()

        # Таблица заказов
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            discipline TEXT,
            subject TEXT,
            work_type TEXT,
            description TEXT,
            deadline TEXT,
            budget REAL,
            final_amount REAL DEFAULT 0,
            payment_url TEXT DEFAULT '',
            plagiarism_required INTEGER DEFAULT 0,
            plagiarism_system TEXT DEFAULT '',
            plagiarism_percent INTEGER DEFAULT 0,
            files TEXT,
            status TEXT DEFAULT 'new',
            payment_status TEXT DEFAULT 'unpaid',
            created_at TEXT,
            expert_id INTEGER DEFAULT 0,
            expert_name TEXT DEFAULT '',
            completed_files TEXT DEFAULT '',
            rating INTEGER DEFAULT 0,
            feedback TEXT DEFAULT '',
            completed_at TEXT,
            tags TEXT DEFAULT ''
        )''')

        # Таблица для логирования действий администратора
        c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            order_id TEXT,
            timestamp TEXT
        )''')

        # Таблица для истории сообщений
        c.execute('''CREATE TABLE IF NOT EXISTS message_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            sender_type TEXT,
            message_text TEXT,
            timestamp TEXT
        )''')

        # Таблица для шаблонов ответов
        c.execute('''CREATE TABLE IF NOT EXISTS response_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            category TEXT DEFAULT 'general'
        )''')

        # Создаем индексы для улучшения производительности
        c.execute('''CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_admin_logs_admin_id ON admin_logs (admin_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_admin_logs_timestamp ON admin_logs (timestamp)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_message_history_order_id ON message_history (order_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_response_templates_category ON response_templates (category)''')

        # Проверяем и добавляем отсутствующие столбцы
        columns_to_add = [
            ('completed_at', 'TEXT'),
            ('payment_status', 'TEXT DEFAULT "unpaid"'),
            ('tags', 'TEXT DEFAULT ""'),
            # Добавьте другие столбцы по необходимости
        ]

        for column_name, column_type in columns_to_add:
            try:
                c.execute(f"ALTER TABLE orders ADD COLUMN {column_name} {column_type}")
            except sqlite3.OperationalError:
                # Столбец уже существует
                pass

        # Добавляем несколько базовых шаблонов ответов
        default_templates = [
            ("Приветствие",
             "Здравствуйте! По вашему заказу #{order_id} найден эксперт. Ожидайте уточнения деталей в ближайшее время.",
             "general"),
            ("Цена назначена",
             "Для вашего заказа #{order_id} назначена цена: {price} руб. Подтвердите и оплатите заказ.", "price"),
            ("Работа завершена", "Ваш заказ #{order_id} выполнен! Файлы готовы к скачиванию.", "completion"),
            ("Доработка", "По вашему заказу #{order_id} требуется дополнительная информация для выполнения работы.",
             "revision"),
            ("Дедлайн", "По вашему заказу #{order_id} установлен дедлайн: {deadline}. Работа будет выполнена вовремя.",
             "deadline")
        ]

        for name, text, category in default_templates:
            try:
                c.execute("INSERT OR IGNORE INTO response_templates (name, text, category) VALUES (?, ?, ?)",
                          (name, text, category))
            except:
                pass

        conn.commit()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise
    finally:
        conn.close()


def get_connection():
    """Получение соединения с базой данных"""
    try:
        conn = sqlite3.connect(Config.DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise


def log_admin_action(admin_id, action, order_id=None):
    """Логирование действий администратора"""
    try:
        conn = get_connection()
        c = conn.cursor()
        timestamp = datetime.now().isoformat()
        c.execute("INSERT INTO admin_logs (admin_id, action, order_id, timestamp) VALUES (?, ?, ?, ?)",
                  (admin_id, action, order_id, timestamp))
        conn.commit()
        logger.info(f"Admin {admin_id}: {action} {f'for order {order_id}' if order_id else ''}")
    except Exception as e:
        logger.error(f"Ошибка логирования действия админа: {e}")
    finally:
        conn.close()


def generate_order_id(user_id):
    """Генерация уникального ID заказа"""
    from datetime import datetime
    import uuid
    date_str = datetime.now().strftime("%d%m")
    return f"{user_id}-{date_str}-{uuid.uuid4().hex[:4]}"


def save_order_to_db(order_data):
    """Сохранение заказа в базу данных"""
    try:
        conn = get_connection()
        c = conn.cursor()

        # Добавьте отладочную информацию
        logger.info(f"Сохранение заказа: {order_data}")

        # Проверяем, существует ли уже заказ с таким ID
        c.execute("SELECT order_id FROM orders WHERE order_id = ?", (order_data['order_id'],))
        existing_order = c.fetchone()

        if existing_order:
            logger.info(f"Заказ {order_data['order_id']} уже существует, обновляем данные")
            # Генерируем новый ID для заказа
            new_order_id = generate_order_id(order_data['user_id'])
            order_data['order_id'] = new_order_id
            logger.info(f"Новый ID заказа: {new_order_id}")

        # Подготавливаем данные
        files = order_data.get('files', [])
        files_str = ",".join([Path(f).name for f in files]) if files else ""
        created_at = datetime.now().isoformat()

        # Устанавливаем значения по умолчанию
        plagiarism_required = order_data.get('plagiarism_required', 0)
        plagiarism_system = order_data.get('plagiarism_system', '')
        plagiarism_percent = order_data.get('plagiarism_percent', 0)
        discipline = order_data.get('discipline', 'Не указано')
        subject = order_data.get('subject', 'Не указано')
        work_type = order_data.get('work_type', 'Не указано')
        description = order_data.get('description', '')
        final_amount = order_data.get('final_amount', 0)
        payment_url = order_data.get('payment_url', '')
        status = order_data.get('status', 'new')
        payment_status = order_data.get('payment_status', 'unpaid')
        expert_id = order_data.get('expert_id', 0)
        expert_name = order_data.get('expert_name', '')
        completed_files = order_data.get('completed_files', '')
        completed_at = order_data.get('completed_at', None)
        tags = order_data.get('tags', '')

        # Вставляем данные
        c.execute('''INSERT INTO orders (
            order_id, user_id, username, discipline, subject, work_type, 
            description, deadline, budget, final_amount, payment_url,
            plagiarism_required, plagiarism_system, plagiarism_percent,
            files, status, payment_status, created_at, expert_id, expert_name, 
            completed_files, completed_at, tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            order_data['order_id'],
            order_data['user_id'],
            order_data['username'],
            discipline,
            subject,
            work_type,
            description,
            order_data['deadline'],
            order_data['budget'],
            final_amount,
            payment_url,
            plagiarism_required,
            plagiarism_system,
            plagiarism_percent,
            files_str,
            status,
            payment_status,
            created_at,
            expert_id,
            expert_name,
            completed_files,
            completed_at,
            tags
        ))

        conn.commit()
        logger.info(f"Заказ {order_data['order_id']} сохранен в БД")
        return order_data['order_id']

    except sqlite3.IntegrityError as e:
        logger.error(f"Ошибка целостности БД при сохранении заказа: {e}")
        # Пытаемся сгенерировать новый ID и сохранить еще раз
        try:
            if 'order_id' in order_data and 'user_id' in order_data:
                order_data['order_id'] = generate_order_id(order_data['user_id'])
                logger.info(f"Повторная попытка сохранения с новым ID: {order_data['order_id']}")
                return save_order_to_db(order_data)
        except:
            pass
        return None
    except Exception as e:
        logger.error(f"Ошибка сохранения заказа: {e}")
        return None
    finally:
        conn.close()


def get_all_orders():
    """Получение всех заказов из базы данных"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT order_id, user_id, username, discipline, work_type, status, deadline, created_at, tags FROM orders ORDER BY created_at DESC")
        orders = c.fetchall()
        return [dict(order) for order in orders]
    except Exception as e:
        logger.error(f"Ошибка получения заказов: {e}")
        return []
    finally:
        conn.close()


def get_order_details(order_id):
    """Получение деталей заказа по ID"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = c.fetchone()

        if order:
            return dict(order)
        return None
    except Exception as e:
        logger.error(f"Ошибка получения деталей заказа: {e}")
        return None
    finally:
        conn.close()


def update_order_price(order_id, price):
    """Обновление цены заказа"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE orders SET final_amount = ? WHERE order_id = ?", (price, order_id))
        conn.commit()
        logger.info(f"Цена заказа {order_id} обновлена на {price}")
    except Exception as e:
        logger.error(f"Ошибка обновления цены: {e}")
    finally:
        conn.close()


def update_order_status(order_id, status):
    """Обновление статуса заказа"""
    try:
        conn = get_connection()
        c = conn.cursor()

        if status == 'completed':
            # При завершении заказа добавляем timestamp
            completed_at = datetime.now().isoformat()
            c.execute("UPDATE orders SET status = ?, completed_at = ? WHERE order_id = ?",
                      (status, completed_at, order_id))
        else:
            c.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))

        conn.commit()
        logger.info(f"Статус заказа {order_id} обновлен на {status}")
    except Exception as e:
        logger.error(f"Ошибка обновления статуса: {e}")
    finally:
        conn.close()


def update_order_completed_files(order_id, files):
    """Обновление списка выполненных файлов заказа"""
    try:
        conn = get_connection()
        c = conn.cursor()
        files_str = ",".join([Path(f).name for f in files]) if files else ""
        c.execute("UPDATE orders SET completed_files = ? WHERE order_id = ?", (files_str, order_id))
        conn.commit()
        logger.info(f"Обновлены выполненные файлы для заказа {order_id}")
    except Exception as e:
        logger.error(f"Ошибка обновления выполненных файлов: {e}")
    finally:
        conn.close()


def update_payment_status(order_id, status):
    """Обновление статуса оплаты заказа"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", (status, order_id))
        conn.commit()
        logger.info(f"Статус оплаты заказа {order_id} обновлен на {status}")
    except Exception as e:
        logger.error(f"Ошибка обновления статуса оплаты: {e}")
    finally:
        conn.close()


def update_payment_url(order_id, payment_url):
    """Обновление платежной ссылки заказа"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE orders SET payment_url = ? WHERE order_id = ?", (payment_url, order_id))
        conn.commit()
        logger.info(f"Платежная ссылка для заказа {order_id} обновлена")
    except Exception as e:
        logger.error(f"Ошибка обновления платежной ссылки: {e}")
    finally:
        conn.close()


def update_order_tags(order_id, tags):
    """Обновление тегов заказа"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE orders SET tags = ? WHERE order_id = ?", (tags, order_id))
        conn.commit()
        logger.info(f"Теги заказа {order_id} обновлены: {tags}")
    except Exception as e:
        logger.error(f"Ошибка обновления тегов: {e}")
    finally:
        conn.close()


def get_user_active_orders_count(user_id):
    """Получение количества активных заказов пользователя"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id = ? AND status IN ('new', 'in_progress', 'waiting_payment', 'paid', 'work_uploaded')",
            (user_id,))
        count = c.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Ошибка получения количества активных заказов: {e}")
        return 0
    finally:
        conn.close()


def get_user_orders(user_id, status=None):
    """Получение заказов пользователя"""
    try:
        conn = get_connection()
        c = conn.cursor()

        if status:
            c.execute("SELECT * FROM orders WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                      (user_id, status))
        else:
            c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))

        orders = c.fetchall()
        return [dict(order) for order in orders]
    except Exception as e:
        logger.error(f"Ошибка получения заказов пользователя: {e}")
        return []
    finally:
        conn.close()


def delete_order(order_id):
    """Удаление заказа"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
        conn.commit()
        logger.info(f"Заказ {order_id} удален")
    except Exception as e:
        logger.error(f"Ошибка удаления заказа: {e}")
    finally:
        conn.close()


def save_message_to_history(order_id, sender_type, message_text):
    """Сохранение сообщения в историю"""
    try:
        conn = get_connection()
        c = conn.cursor()
        timestamp = datetime.now().isoformat()
        c.execute("INSERT INTO message_history (order_id, sender_type, message_text, timestamp) VALUES (?, ?, ?, ?)",
                  (order_id, sender_type, message_text, timestamp))
        conn.commit()
        logger.info(f"Сообщение для заказа {order_id} сохранено в историю")
    except Exception as e:
        logger.error(f"Ошибка сохранения сообщения: {e}")
    finally:
        conn.close()


def get_message_history(order_id):
    """Получение истории сообщений по заказу"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM message_history WHERE order_id = ? ORDER BY timestamp", (order_id,))
        messages = c.fetchall()
        return [dict(message) for message in messages]
    except Exception as e:
        logger.error(f"Ошибка получения истории сообщений: {e}")
        return []
    finally:
        conn.close()


def get_response_templates(category=None):
    """Получение шаблонов ответов"""
    try:
        conn = get_connection()
        c = conn.cursor()

        if category:
            c.execute("SELECT * FROM response_templates WHERE category = ? ORDER BY name", (category,))
        else:
            c.execute("SELECT * FROM response_templates ORDER BY category, name")

        templates = c.fetchall()
        return [dict(template) for template in templates]
    except Exception as e:
        logger.error(f"Ошибка получения шаблонов ответов: {e}")
        return []
    finally:
        conn.close()


def save_response_template(name, text, category='general'):
    """Сохранение шаблона ответа"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO response_templates (name, text, category) VALUES (?, ?, ?)",
                  (name, text, category))
        conn.commit()
        logger.info(f"Шаблон ответа '{name}' сохранен")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения шаблона ответа: {e}")
        return False
    finally:
        conn.close()


def get_orders_by_tags(tags):
    """Получение заказов по тегам"""
    try:
        conn = get_connection()
        c = conn.cursor()

        tag_list = tags.split(',')
        placeholders = ','.join(['?'] * len(tag_list))

        # Ищем заказы, содержащие все указанные теги
        query = f"""
        SELECT * FROM orders 
        WHERE tags LIKE '%' || ? || '%'
        """

        for tag in tag_list[1:]:
            query += f" AND tags LIKE '%' || ? || '%'"

        query += " ORDER BY created_at DESC"

        c.execute(query, tag_list)
        orders = c.fetchall()
        return [dict(order) for order in orders]
    except Exception as e:
        logger.error(f"Ошибка получения заказов по тегам: {e}")
        return []
    finally:
        conn.close()