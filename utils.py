import logging
import re
import os
import uuid
import asyncio
import functools
from pathlib import Path
from datetime import datetime
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
            file_ext = Path(file.file_name).suffix if hasattr(file, 'file_name') else '.jpg'
            file_name = f"{uuid.uuid4().hex[:8]}{file_ext}"

        file_path = order_folder / file_name

        # Проверяем, существует ли файл с таким именем
        counter = 1
        original_name = file_path.stem
        while file_path.exists():
            file_name = f"{original_name}_{counter}{file_path.suffix}"
            file_path = order_folder / file_name
            counter += 1

        # ИСПРАВЛЕННАЯ СТРОКА - используем download_to_drive
        await file.download_to_drive(custom_path=str(file_path))

        if file_path.exists() and file_path.stat().st_size > 0:
            return str(file_path)
        return None
    except Exception as e:
        logger.error(f"Ошибка сохранения файла: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка сохранения файла: {e}")
        return None


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