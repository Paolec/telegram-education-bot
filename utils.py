import logging
import re
import os
import uuid
import asyncio
import functools
import shutil
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from io import BytesIO
from telegram import Update
from telegram.ext import CallbackContext
from config import Config

logger = logging.getLogger(__name__)


def generate_order_id(user_id):
    """Генерация уникального ID заказа"""
    date_str = datetime.now().strftime("%d%m")
    return f"{user_id}-{date_str}-{uuid.uuid4().hex[:4]}"


def create_order_folder(order_id, user_id, folder_type="uploads"):
    """Создание папки для файлов заказа"""
    try:
        if folder_type == "completed":
            base_path = Path(Config.COMPLETED_FOLDER) / str(user_id) / order_id
        else:
            base_path = Path(Config.BASE_UPLOAD_FOLDER) / str(user_id) / order_id

        base_path.mkdir(exist_ok=True, parents=True)
        return base_path
    except Exception as e:
        logger.error(f"Ошибка создания папки: {e}")
        return None


async def save_file(file, order_folder, file_name=None):
    """Сохранение загруженного файла"""
    try:
        if not order_folder or not order_folder.exists():
            return None

        if not file_name:
            # Определяем расширение файла
            if hasattr(file, 'file_name') and file.file_name:
                file_ext = Path(file.file_name).suffix
            else:
                # Для фото используем jpg
                file_ext = '.jpg'
            file_name = f"{uuid.uuid4().hex[:8]}{file_ext}"

        file_path = order_folder / file_name

        # Проверяем, существует ли файл с таким именем
        counter = 1
        original_name = file_path.stem
        while file_path.exists():
            file_name = f"{original_name}_{counter}{file_path.suffix}"
            file_path = order_folder / file_name
            counter += 1

        # Получаем объект File из документа или фото
        if hasattr(file, 'file_id'):
            file_obj = await file.get_file()
            await file_obj.download_to_drive(custom_path=file_path)
        else:
            # Для фото
            await file.download_to_drive(custom_path=file_path)

        if file_path.exists() and file_path.stat().st_size > 0:
            return str(file_path)
        return None
    except Exception as e:
        logger.error(f"Ошибка сохранения файла: {e}")
        return None


async def create_zip_archive(files, archive_name="files.zip"):
    """Создание ZIP-архива из файлов"""
    try:
        # Создаем архив в памяти
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in files:
                if Path(file_path).exists():
                    zip_file.write(file_path, Path(file_path).name)

        zip_buffer.seek(0)
        return zip_buffer
    except Exception as e:
        logger.error(f"Ошибка создания архива: {e}")
        return None


async def send_files_as_archive(update, context, files, caption):
    """Отправка файлов в виде архива"""
    try:
        if len(files) > 1:
            # Создаем архив если файлов несколько
            archive = await create_zip_archive(files, "files.zip")
            if archive:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=archive,
                    filename="files.zip",
                    caption=caption
                )
                return True

        # Если файл один или не удалось создать архив, отправляем по отдельности
        for file_path in files:
            if Path(file_path).exists():
                with open(file_path, 'rb') as file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=file,
                        caption=caption if len(files) == 1 else None
                    )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки файлов: {e}")
        return False


async def split_long_message(text, max_length=Config.MAX_MESSAGE_LENGTH):
    """Разделение длинного сообщения на части"""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        # Ищем место для разрыва сообщения
        break_index = text.rfind('\n', 0, max_length)
        if break_index == -1:
            break_index = text.rfind(' ', 0, max_length)
        if break_index == -1:
            break_index = max_length

        parts.append(text[:break_index])
        text = text[break_index:].lstrip()

    return parts


def validate_deadline(deadline_str):
    """Проверка корректности даты дедлайна"""
    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', deadline_str):
        return False, "Неверный формат. Используйте ДД.ММ.ГГГГ (например, 25.08.2025)"

    try:
        deadline_date = datetime.strptime(deadline_str, "%d.%m.%Y")
        if deadline_date < datetime.now():
            return False, "Дата не может быть в прошлом!"
        return True, deadline_date
    except ValueError:
        return False, "Неверный формат даты"


def validate_budget(budget_str):
    """Проверка корректности бюджета"""
    try:
        budget_value = float(budget_str)
        if budget_value <= 0:
            return False, "Бюджет должен быть положительным числом"

        if budget_value < Config.MIN_BUDGET:
            return False, f"Минимальная сумма заказа - {Config.MIN_BUDGET} руб. Укажите большую сумму:"

        return True, budget_value
    except ValueError:
        return False, "Неверный формат бюджета. Укажите число:"


def validate_plagiarism_percent(percent_str):
    """Проверка корректности процента антиплагиата"""
    try:
        percent_value = int(percent_str)
        if percent_value < 0 or percent_value > 100:
            return False, "Неверный формат. Укажите число от 0 до 100:"
        return True, percent_value
    except ValueError:
        return False, "Неверный формат. Укажите число от 0 до 100:"


def with_retry(max_retries=3, delay=1):
    """Декоратор для повторных попыток выполнения функции"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Попытка {attempt + 1} из {max_retries} не удалась: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay * (attempt + 1))
            logger.error(f"Все {max_retries} попыток не удались: {last_exception}")
            raise last_exception

        return wrapper

    return decorator


def log_errors(func):
    """Декоратор для логирования ошибок"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка в функции {func.__name__}: {e}")
            # Отправляем уведомление администратору о критической ошибке
            try:
                update = args[0] if args else None
                if update and hasattr(update, 'message'):
                    await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
            except:
                pass
            raise

    return wrapper


async def handle_wrong_input(update, context):
    """Обработка неправильного ввода"""
    await update.message.reply_text("Пожалуйста, введите текстовое сообщение.")
    return context._current_state


async def check_deadlines(context: CallbackContext):
    """Проверка дедлайнов и отправка напоминаний"""
    try:
        from database import get_all_orders, get_order_details

        orders = get_all_orders()
        in_progress_orders = [order for order in orders if order['status'] == 'in_progress']

        for order in in_progress_orders:
            order_details = get_order_details(order['order_id'])

            if not order_details:
                continue

            try:
                deadline = datetime.strptime(order_details['deadline'], "%d.%m.%Y")
                days_until_deadline = (deadline - datetime.now()).days

                # Отправляем напоминание за 1, 3 и 7 дней до дедлайна
                if days_until_deadline in [1, 3, 7]:
                    message = (
                        f"⏰ Напоминание о дедлайне\n\n"
                        f"Заказ #{order_details['order_id']}\n"
                        f"До дедлайна осталось: {days_until_deadline} день(дней)\n"
                        f"Дата выполнения: {order_details['deadline']}\n\n"
                        f"Пожалуйста, убедитесь, что работа будет выполнена вовремя."
                    )

                    # Отправляем студенту
                    await context.bot.send_message(
                        chat_id=order_details['user_id'],
                        text=message
                    )

                    # Отправляем администратору
                    await context.bot.send_message(
                        chat_id=Config.ADMIN_ID,
                        text=f"⏰ Напоминание: {message}"
                    )

            except ValueError:
                logger.error(f"Неверный формат даты в заказе {order_details['order_id']}")

    except Exception as e:
        logger.error(f"Ошибка проверки дедлайнов: {e}")


async def error_handler(update: object, context: CallbackContext) -> None:
    """Обработка ошибок"""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Отправляем сообщение об ошибке пользователю
    if update and isinstance(update, Update):
        try:
            if update.message:
                await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")

    # Отправляем уведомление администратору
    try:
        error_message = (
            f"⚠️ Произошла ошибка в боте:\n\n"
            f"Ошибка: {context.error}\n"
            f"Данные: {context.user_data}\n"
            f"Чат: {update.effective_chat.id if update and hasattr(update, 'effective_chat') else 'N/A'}"
        )

        # Разбиваем длинное сообщение на части
        error_parts = await split_long_message(error_message)
        for part in error_parts:
            await context.bot.send_message(chat_id=Config.ADMIN_ID, text=part)

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")


def is_file_available(completed_at):
    """Проверяет, доступен ли файл для скачивания (не прошло ли 30 дней)"""
    if not completed_at:
        return False

    try:
        completed_date = datetime.fromisoformat(completed_at)
        current_date = datetime.now()
        days_passed = (current_date - completed_date).days
        return days_passed <= 30
    except ValueError:
        return False


async def cleanup_old_files(context: CallbackContext):
    """Очистка файлов старше 30 дней"""
    try:
        from database import get_all_orders

        orders = get_all_orders()
        current_time = datetime.now()

        for order in orders:
            if order['status'] == 'completed' and order.get('completed_at'):
                try:
                    completed_date = datetime.fromisoformat(order['completed_at'])
                    days_passed = (current_time - completed_date).days

                    if days_passed > 30:
                        # Удаляем папку с выполненной работой
                        completed_folder = create_order_folder(
                            order['order_id'],
                            order['user_id'],
                            "completed"
                        )

                        if completed_folder and completed_folder.exists():
                            shutil.rmtree(completed_folder)
                            logger.info(f"Удалена папка с выполненной работой для заказа {order['order_id']}")

                except ValueError:
                    continue

    except Exception as e:
        logger.error(f"Ошибка при очистке старых файлов: {e}")


async def create_backup(context: CallbackContext):
    """Создание резервной копии базы данных"""
    try:
        from config import Config

        if not Config.BACKUP_ENABLED:
            return

        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)

        # Создаем имя файла с датой
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.db"

        # Копируем базу данных
        import shutil
        shutil.copy2(Config.DB_NAME, backup_file)

        # Удаляем старые резервные копии (оставляем последние 7)
        backup_files = sorted(backup_dir.glob("backup_*.db"), key=os.path.getmtime)
        for old_backup in backup_files[:-7]:
            old_backup.unlink()

        logger.info(f"Создана резервная копия: {backup_file}")

        # Отправляем уведомление администратору
        try:
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text=f"✅ Создана резервная копия базы данных: {backup_file.name}"
            )
        except:
            pass

    except Exception as e:
        logger.error(f"Ошибка создания резервной копии: {e}")


def format_order_details(order):
    """Форматирование деталей заказа для отображения"""
    if not order:
        return "Заказ не найден."

    order_details = (
        f"📋 Заказ #{order['order_id']}\n"
        f"👤 Студент: @{order['username']} (ID: {order['user_id']})\n"
        f"📚 Дисциплина: {order['discipline']}\n"
        f"📝 Тип работы: {order['work_type']}\n"
        f"📅 Дедлайн: {order['deadline']}\n"
        f"💰 Бюджет: {order['budget']} руб.\n"
        f"💵 Итоговая цена: {order['final_amount']} руб.\n"
        f"📄 Описание: {order['description']}\n"
        f"🏷️ Теги: {order.get('tags', 'Нет')}\n"
        f"🔄 Статус: {Config.ORDER_STATUSES.get(order['status'], order['status'])}\n"
    )

    # Добавляем информацию о антиплагиате, если требуется
    if order['plagiarism_required']:
        plagiarism_system = Config.PLAGIARISM_SYSTEMS.get(order['plagiarism_system'], {}).get('name', 'Не указана')
        order_details += f"🔍 Система антиплагиата: {plagiarism_system}\n"
        order_details += f"📊 Требуемый процент: {order['plagiarism_percent']}%\n"

    # Добавляем информацию о файлах
    if order['files']:
        order_details += f"📎 Файлы: {order['files']}\n"

    # Добавляем информацию о времени завершения, если заказ завершен
    if order['status'] == 'completed' and order.get('completed_at'):
        order_details += f"✅ Завершен: {order['completed_at'][:10]}\n"

    return order_details


def get_file_size(file_path):
    """Получение размера файла в читаемом формате"""
    size = os.path.getsize(file_path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def validate_email(email):
    """Проверка корректности email адреса"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def format_timedelta(td):
    """Форматирование временного интервала в читаемый вид"""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{days} дн. {hours} ч. {minutes} мин."
    elif hours > 0:
        return f"{hours} ч. {minutes} мин."
    elif minutes > 0:
        return f"{minutes} мин. {seconds} сек."
    else:
        return f"{seconds} сек."


def delete_order_files(order_id, user_id):
    """Полное удаление всех файлов заказа"""
    try:
        # Удаляем папку с загруженными файлами
        upload_folder = create_order_folder(order_id, user_id, "uploads")
        if upload_folder and upload_folder.exists():
            shutil.rmtree(upload_folder)

        # Удаляем папку с выполненной работой
        completed_folder = create_order_folder(order_id, user_id, "completed")
        if completed_folder and completed_folder.exists():
            shutil.rmtree(completed_folder)

        logger.info(f"Файлы заказа #{order_id} полностью удалены")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления файлов заказа #{order_id}: {e}")
        return False


async def notify_student(context: CallbackContext, user_id, message):
    """Отправка уведомления студенту"""
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления студенту {user_id}: {e}")
        return False


async def generate_payment_link(order_id, amount, user_id, description):
    """Генерация платежной ссылки"""
    try:
        from payment import generate_robokassa_payment_link
        payment_url = generate_robokassa_payment_link(
            order_id=order_id,
            amount=amount,
            description=description,
            user_id=user_id
        )
        return payment_url
    except Exception as e:
        logger.error(f"Ошибка генерации платежной ссылки: {e}")
        return None


def validate_price(price_str):
    """Проверка корректности цены"""
    try:
        price_value = float(price_str)
        if price_value <= 0:
            return False, "Цена должна быть положительным числом"

        if price_value < Config.MIN_BUDGET:
            return False, f"Минимальная цена - {Config.MIN_BUDGET} руб. Укажите большую сумму:"

        return True, price_value
    except ValueError:
        return False, "Неверный формат цены. Укажите число:"