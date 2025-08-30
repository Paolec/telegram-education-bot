# admin_handlers.py - обработчики для админ-панели
import logging
import os
import pyotp
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from config import Config
import database
import utils
from keyboards import (
    get_admin_main_keyboard,
    get_admin_order_actions_keyboard,
    get_admin_orders_navigation_keyboard,
    get_admin_all_orders_keyboard,
    get_student_confirmation_keyboard
)

logger = logging.getLogger(__name__)

# Состояния разговора для админ-панели
(
    ADMIN_MAIN, ADMIN_VIEW_ORDERS, ADMIN_ORDER_DETAILS, ADMIN_SEND_MESSAGE,
    ADMIN_SET_PRICE, ADMIN_UPLOAD_WORK, ADMIN_2FA_VERIFICATION, ADMIN_MANAGE_TAGS,
    ADMIN_MANAGE_TEMPLATES, ADMIN_CREATE_TEMPLATE
) = range(10)

# Категории для шаблонов ответов
TEMPLATE_CATEGORIES = {
    'general': '📋 Общие',
    'price': '💰 Ценообразование',
    'deadline': '⏰ Сроки',
    'completion': '✅ Завершение работ',
    'revision': '🔄 Доработки'
}


async def admin_start(update: Update, context: CallbackContext):
    """Начало работы с админ-панелью"""
    user_id = update.effective_user.id

    # Проверяем, является ли пользователь администратором
    if user_id != Config.ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к админ-панели.")
        return ConversationHandler.END

    # Проверяем, включена ли 2FA и нужно ли запрашивать код
    if Config.ENABLE_2FA and not context.user_data.get('admin_2fa_verified'):
        # Генерируем и отправляем код
        totp = pyotp.TOTP(Config.ADMIN_2FA_SECRET)
        current_code = totp.now()

        # Сохраняем ожидаемый код в контексте
        context.user_data['admin_2fa_code'] = current_code
        context.user_data['admin_2fa_expires'] = datetime.now() + timedelta(minutes=5)

        await update.message.reply_text(
            "🔐 Для входа в админ-панель введите код двухфакторной аутентификации:"
        )
        return ADMIN_2FA_VERIFICATION

    # Логируем вход в админ-панель
    database.log_admin_action(user_id, "admin_login")

    await update.message.reply_text(
        "👋 Добро пожаловать в админ-панель!\n\n"
        "Здесь вы можете управлять заказами и взаимодействовать со студентами.",
        reply_markup=get_admin_main_keyboard()
    )

    return ADMIN_MAIN


async def admin_verify_2fa(update: Update, context: CallbackContext):
    """Проверка кода двухфакторной аутентификации"""
    user_code = update.message.text.strip()
    expected_code = context.user_data.get('admin_2fa_code')
    expires = context.user_data.get('admin_2fa_expires')

    if not expected_code or datetime.now() > expires:
        await update.message.reply_text("❌ Код устарел. Попробуйте войти снова.")
        return ConversationHandler.END

    if user_code == expected_code:
        context.user_data['admin_2fa_verified'] = True
        # Логируем вход в админ-панель
        database.log_admin_action(update.effective_user.id, "admin_login_2fa")

        await update.message.reply_text(
            "✅ Код верный! Добро пожаловать в админ-панель.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
    else:
        await update.message.reply_text("❌ Неверный код. Попробуйте еще раз:")
        return ADMIN_2FA_VERIFICATION


async def admin_start_from_query(update: Update, context: CallbackContext):
    """Начало работы с админ-панелью из callback query"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Проверяем, является ли пользователь администратором
    if user_id != Config.ADMIN_ID:
        await query.edit_message_text("У вас нет доступа к админ-панели.")
        return ConversationHandler.END

    # Проверяем, включена ли 2FA и нужно ли запрашивать код
    if Config.ENABLE_2FA and not context.user_data.get('admin_2fa_verified'):
        # Генерируем и отправляем код
        totp = pyotp.TOTP(Config.ADMIN_2FA_SECRET)
        current_code = totp.now()

        # Сохраняем ожидаемый код в контексте
        context.user_data['admin_2fa_code'] = current_code
        context.user_data['admin_2fa_expires'] = datetime.now() + timedelta(minutes=5)

        await query.edit_message_text(
            "🔐 Для входа в админ-панель введите код двухфакторной аутентификации:"
        )
        return ADMIN_2FA_VERIFICATION

    # Логируем вход в админ-панель
    database.log_admin_action(user_id, "admin_login")

    await query.edit_message_text(
        "👋 Добро пожаловать в админ-панель!\n\n"
        "Здесь вы можете управлять заказами и взаимодействовать со студентами.",
        reply_markup=get_admin_main_keyboard()
    )

    return ADMIN_MAIN


async def admin_cancel(update: Update, context: CallbackContext):
    """Отмена действия в админ-панели"""
    user_id = update.effective_user.id

    # Логируем отмену действия
    database.log_admin_action(user_id, "admin_cancel")

    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=get_admin_main_keyboard()
    )

    return ADMIN_MAIN


async def admin_view_all_orders(update: Update, context: CallbackContext):
    """Просмотр всех заказов"""
    query = update.callback_query
    await query.answer()

    # Логируем действие
    database.log_admin_action(update.effective_user.id, "view_all_orders")

    # Получаем все заказы
    orders = database.get_all_orders()

    if not orders:
        await query.edit_message_text(
            "Заказов не найдено.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Сохраняем заказы в контексте для пагинации
    context.user_data['all_orders'] = orders
    context.user_data['all_orders_page'] = 0

    # Показываем первую страницу
    return await show_all_orders_page(update, context, 0)


async def show_all_orders_page(update: Update, context: CallbackContext, page=0):
    """Показать страницу со всеми заказами"""
    orders = context.user_data.get('all_orders', [])
    orders_per_page = 5
    total_pages = (len(orders) + orders_per_page - 1) // orders_per_page

    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0

    context.user_data['all_orders_page'] = page

    # Получаем заказы для текущей страницы
    start_idx = page * orders_per_page
    end_idx = min((page + 1) * orders_per_page, len(orders))
    current_orders = orders[start_idx:end_idx]

    message = "📋 Все заказы:\n\n"

    for i, order in enumerate(current_orders, start_idx + 1):
        status_emoji = {
            'new': '🔍',
            'in_progress': '🛠',
            'completed': '✅',
            'cancelled': '❌',
            'waiting_payment': '💳',
            'paid': '💰',
            'work_uploaded': '📤',
            'revision_requested': '🔄'
        }.get(order.get('status', ''), '❓')

        # Используем get() для безопасного доступа к полям
        budget = order.get('budget', 0)
        discipline = order.get('discipline', 'Не указано')
        work_type = order.get('work_type', 'Не указано')
        deadline = order.get('deadline', 'Не указано')
        username = order.get('username', 'Не указано')

        message += (
            f"{i}. {status_emoji} Заказ #{order.get('order_id', 'N/A')}\n"
            f"   👤 @{username} | {discipline}\n"
            f"   📝 {work_type} | {deadline}\n"
            f"   💰 {budget} руб. | {Config.ORDER_STATUSES.get(order.get('status', ''), order.get('status', ''))}\n\n"
        )

    message += f"Страница {page + 1}/{total_pages}"

    await update.callback_query.edit_message_text(
        message,
        reply_markup=get_admin_all_orders_keyboard(current_orders, page, total_pages)
    )

    return ADMIN_VIEW_ORDERS


async def admin_orders_by_status(update: Update, context: CallbackContext):
    """Просмотр заказов по статусу"""
    query = update.callback_query
    await query.answer()

    status = query.data.replace("admin_orders_", "")
    context.user_data['orders_status'] = status
    context.user_data['orders_page'] = 0

    # Получаем заказы по статусу
    orders = get_orders_by_status(status)

    if not orders:
        await query.edit_message_text(
            f"Заказов со статусом '{Config.ORDER_STATUSES.get(status, status)}' не найдено.",
            reply_markup=get_admin_orders_navigation_keyboard(status, 0, 1)
        )
        return ADMIN_VIEW_ORDERS

    # Рассчитываем общее количество страниц
    total_pages = (len(orders) + 4) // 5  # 5 заказов на страницу

    # Получаем заказы для текущей страницы
    start_idx = 0
    end_idx = min(5, len(orders))
    current_orders = orders[start_idx:end_idx]

    # Формируем сообщение
    message = f"📋 Заказы со статусом: {Config.ORDER_STATUSES.get(status, status)}\n\n"

    for i, order in enumerate(current_orders, 1):
        # Используем get() для безопасного доступа к полям
        tags = order.get('tags', '')
        tags_display = f" 🏷️{tags}" if tags else ""
        budget = order.get('budget', 0)
        username = order.get('username', 'Не указано')
        discipline = order.get('discipline', 'Не указано')
        work_type = order.get('work_type', 'Не указано')
        deadline = order.get('deadline', 'Не указано')

        message += (
            f"{i}. Заказ #{order.get('order_id', 'N/A')}{tags_display}\n"
            f"   👤 Студент: @{username}\n"
            f"   📚 Дисциплина: {discipline}\n"
            f"   📝 Тип работы: {work_type}\n"
            f"   📅 Дедлайн: {deadline}\n"
            f"   💰 Бюджет: {budget} руб.\n\n"
        )

    message += f"Страница 1/{total_pages}"

    await query.edit_message_text(
        message,
        reply_markup=get_admin_orders_navigation_keyboard(status, 0, total_pages)
    )

    return ADMIN_VIEW_ORDERS


async def admin_handle_orders_navigation(update: Update, context: CallbackContext):
    """Обработка навигации по заказам"""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split("_")
    action = data_parts[2]  # prev или next
    status = data_parts[3]  # статус заказов
    page = int(data_parts[4])  # номер страницы

    context.user_data['orders_status'] = status
    context.user_data['orders_page'] = page

    # Получаем заказы по статусу
    orders = get_orders_by_status(status)

    if not orders:
        await query.edit_message_text(
            f"Заказов со статусом '{Config.ORDER_STATUSES.get(status, status)}' не найдено.",
            reply_markup=get_admin_orders_navigation_keyboard(status, page, 1)
        )
        return ADMIN_VIEW_ORDERS

    # Рассчитываем общее количество страниц
    total_pages = (len(orders) + 4) // 5  # 5 заказов на страницу

    # Получаем заказы для текущей страницу
    start_idx = page * 5
    end_idx = min((page + 1) * 5, len(orders))
    current_orders = orders[start_idx:end_idx]

    # Формируем сообщение
    message = f"📋 Заказы со статусом: {Config.ORDER_STATUSES.get(status, status)}\n\n"

    for i, order in enumerate(current_orders, 1):
        # Используем get() для безопасного доступа к полям
        tags = order.get('tags', '')
        tags_display = f" 🏷️{tags}" if tags else ""
        budget = order.get('budget', 0)
        username = order.get('username', 'Не указано')
        discipline = order.get('discipline', 'Не указано')
        work_type = order.get('work_type', 'Не указано')
        deadline = order.get('deadline', 'Не указано')

        message += (
            f"{i + start_idx}. Заказ #{order.get('order_id', 'N/A')}{tags_display}\n"
            f"   👤 Студент: @{username}\n"
            f"   📚 Дисциплина: {discipline}\n"
            f"   📝 Тип работы: {work_type}\n"
            f"   📅 Дедлайн: {deadline}\n"
            f"   💰 Бюджет: {budget} руб.\n\n"
        )

    message += f"Страница {page + 1}/{total_pages}"

    await query.edit_message_text(
        message,
        reply_markup=get_admin_orders_navigation_keyboard(status, page, total_pages)
    )

    return ADMIN_VIEW_ORDERS


async def admin_order_details(update: Update, context: CallbackContext):
    """Просмотр деталей заказа администратором"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('admin_order_', '')
    context.user_data['current_order_id'] = order_id

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if not order:
        await query.edit_message_text("Заказ не найден.")
        return ADMIN_VIEW_ORDERS

    # Формируем сообщение с деталями заказа
    order_details = (
        f"📋 Заказ #{order.get('order_id', 'N/A')}\n"
        f"👤 Студент: @{order.get('username', 'Не указано')} (ID: {order.get('user_id', 'Не указано')})\n"
        f"📚 Дисциплина: {order.get('discipline', 'Не указано')}\n"
        f"📝 Тип работы: {order.get('work_type', 'Не указано')}\n"
        f"📅 Дедлайн: {order.get('deadline', 'Не указано')}\n"
        f"💰 Бюджет: {order.get('budget', 0)} руб.\n"
        f"💵 Итоговая цена: {order.get('final_amount', 0)} руб.\n"
        f"📄 Описание: {order.get('description', 'Нет описания')}\n"
        f"🏷️ Теги: {order.get('tags', 'Нет')}\n"
        f"🔄 Статус: {Config.ORDER_STATUSES.get(order.get('status', ''), order.get('status', ''))}\n"
    )

    # Добавляем информацию о антиплагиате, если требуется
    if order.get('plagiarism_required', False):
        plagiarism_system = Config.PLAGIARISM_SYSTEMS.get(order.get('plagiarism_system', ''), {}).get('name',
                                                                                                      'Не указана')
        order_details += f"🔍 Система антиплагиата: {plagiarism_system}\n"
        order_details += f"📊 Требуемый процент: {order.get('plagiarism_percent', 0)}%\n"

    # Добавляем информацию о файлах
    if order.get('files'):
        order_details += f"📎 Файлы: {order.get('files', 'Нет файлов')}\n"

    # Добавляем информацию о времени завершения, если заказ завершен
    if order.get('status') == 'completed' and order.get('completed_at'):
        order_details += f"✅ Завершен: {order.get('completed_at', '')[:10]}\n"

    # Отправляем сообщение с деталями заказа
    await query.edit_message_text(
        order_details,
        reply_markup=get_admin_order_actions_keyboard(order_id)
    )

    # Если есть файлы, отправляем их администратору
    if order.get('files'):
        try:
            user_id = order.get('user_id')
            order_folder = utils.create_order_folder(order_id, user_id)

            if order_folder and order_folder.exists():
                files = list(order_folder.glob('*'))

                # Если файлов больше одного, отправляем архив
                if len(files) > 1:
                    from utils import send_files_as_archive
                    await send_files_as_archive(
                        update, context, files,
                        f"Файлы заказа #{order_id}"
                    )
                else:
                    # Отправляем файлы по одному
                    for file in files:
                        if file.is_file():
                            try:
                                await context.bot.send_document(
                                    chat_id=query.message.chat_id,
                                    document=open(file, 'rb'),
                                    caption=f"Файл из заказа #{order_id}: {file.name}"
                                )
                            except Exception as e:
                                logger.error(f"Ошибка отправки файла {file.name}: {e}")
        except Exception as e:
            logger.error(f"Ошибка получения файлов заказа: {e}")
            await query.message.reply_text("❌ Ошибка при получении файлов заказа.")

    return ADMIN_ORDER_DETAILS


async def admin_handle_message(update: Update, context: CallbackContext):
    """Обработка ввода сообщения для студента"""
    # Проверяем, есть ли сообщение в update
    if not update.message:
        await update.callback_query.answer("Ошибка: сообщение не найдено.")
        return ADMIN_ORDER_DETAILS

    order_id = context.user_data.get('current_order_id')

    if not order_id:
        await update.message.reply_text("Ошибка: не выбран заказ.")
        return ADMIN_MAIN

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if not order:
        await update.message.reply_text("Заказ не найден.")
        return ADMIN_VIEW_ORDERS

    message_text = ""

    # Обрабатываем текстовые сообщения
    if update.message.text:
        message_text = update.message.text
    # Обрабатываем голосовые сообщения
    elif update.message.voice:
        voice = update.message.voice
        voice_file = await voice.get_file()
        # Сохраняем голосовое сообщение
        voice_path = f"voices/{order_id}_{voice.file_id}.ogg"
        os.makedirs(os.path.dirname(voice_path), exist_ok=True)
        await voice_file.download_to_drive(voice_path)
        message_text = "🎤 Голосовое сообщение"

        # Отправляем голосовое сообщение студенту
        try:
            await context.bot.send_voice(
                chat_id=order.get('user_id'),
                voice=open(voice_path, 'rb'),
                caption=f"Голосовое сообщение по заказу #{order_id}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки голосового сообщения: {e}")
            await update.message.reply_text("❌ Не удалось отправить голосовое сообщение.")
            return ADMIN_ORDER_DETAILS

    if message_text:
        # Отправляем текстовое сообщение студенту
        try:
            await context.bot.send_message(
                chat_id=order.get('user_id'),
                text=f"📩 Сообщение от эксперта по заказу #{order_id}:\n\n{message_text}"
            )

            # Сохраняем сообщение в историю
            database.save_message_to_history(order_id, "admin", message_text)

            # Логируем действие
            database.log_admin_action(update.effective_user.id, f"send_message_{order_id}", order_id)

            await update.message.reply_text(
                f"✅ Сообщение отправлено студенту @{order.get('username', 'Не указано')}.",
                reply_markup=get_admin_order_actions_keyboard(order_id)
            )

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения студенту: {e}")
            await update.message.reply_text(
                "❌ Не удалось отправить сообщение студенту. Возможно, он заблокировал бота.",
                reply_markup=get_admin_order_actions_keyboard(order_id)
            )

    return ADMIN_ORDER_DETAILS


async def admin_manage_tags(update: Update, context: CallbackContext):
    """Управление тегами заказа"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('admin_tags_', '')
    context.user_data['current_order_id'] = order_id

    order = database.get_order_details(order_id)
    current_tags = order.get('tags', '')

    await query.edit_message_text(
        f"🏷️ Управление тегами заказа #{order_id}\n\n"
        f"Текущие теги: {current_tags}\n\n"
        "Введите новые теги через запятую:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data=f"admin_order_{order_id}")]
        ])
    )

    return ADMIN_MANAGE_TAGS


async def admin_handle_tags(update: Update, context: CallbackContext):
    """Обработка ввода тегов"""
    order_id = context.user_data.get('current_order_id')
    new_tags = update.message.text.strip()

    # Обновляем теги в базе
    database.update_order_tags(order_id, new_tags)

    # Логируем действие
    database.log_admin_action(update.effective_user.id, f"update_tags_{new_tags}", order_id)

    await update.message.reply_text(
        f"✅ Теги заказа #{order_id} обновлены: {new_tags}",
        reply_markup=get_admin_order_actions_keyboard(order_id)
    )

    return ADMIN_ORDER_DETAILS


async def admin_manage_templates(update: Update, context: CallbackContext):
    """Управление шаблонами ответов"""
    query = update.callback_query
    await query.answer()

    templates = database.get_response_templates()

    if not templates:
        message = "📝 Шаблоны ответов\n\nШаблонов пока нет."
        keyboard = [
            [InlineKeyboardButton("➕ Создать шаблон", callback_data="admin_create_template")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
    else:
        message = "📝 Шаблоны ответов\n\n"
        keyboard = []

        # Группируем шаблоны по категориям
        templates_by_category = {}
        for template in templates:
            category = template['category']
            if category not in templates_by_category:
                templates_by_category[category] = []
            templates_by_category[category].append(template)

        # Добавляем шаблоны по категориям
        for category, category_templates in templates_by_category.items():
            category_name = TEMPLATE_CATEGORIES.get(category, category)
            message += f"{category_name}:\n"

            for template in category_templates:
                message += f"  • {template['name']}\n"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{category_name} - {template['name']}",
                        callback_data=f"admin_use_template_{template['id']}"
                    )
                ])

            message += "\n"

        keyboard.append([InlineKeyboardButton("➕ Создать шаблон", callback_data="admin_create_template")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ADMIN_MANAGE_TEMPLATES


async def admin_create_template(update: Update, context: CallbackContext):
    """Создание нового шаблона ответа"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📝 Создание нового шаблона ответа\n\n"
        "Введите название шаблона:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_manage_templates")]
        ])
    )

    return ADMIN_CREATE_TEMPLATE


async def admin_handle_template_name(update: Update, context: CallbackContext):
    """Обработка ввода названия шаблона"""
    template_name = update.message.text.strip()
    context.user_data['new_template_name'] = template_name

    # Создаем клавиатуру для выбора категории
    keyboard = []
    for category_id, category_name in TEMPLATE_CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(category_name, callback_data=f"admin_template_category_{category_id}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_manage_templates")])

    await update.message.reply_text(
        "Выберите категорию для шаблона:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ADMIN_CREATE_TEMPLATE


async def admin_handle_template_category(update: Update, context: CallbackContext):
    """Обработка выбора категории шаблона"""
    query = update.callback_query
    await query.answer()

    category = query.data.replace('admin_template_category_', '')
    context.user_data['new_template_category'] = category

    await query.edit_message_text(
        "Введите текст шаблона:\n\n"
        "Можно использовать плейсхолдер {order_id} для автоматической подстановки номера заказа.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_manage_templates")]
        ])
    )

    return ADMIN_CREATE_TEMPLATE


async def admin_handle_template_text(update: Update, context: CallbackContext):
    """Обработка ввода текста шаблона"""
    template_text = update.message.text.strip()

    # Сохраняем шаблон в базу данных
    name = context.user_data.get('new_template_name')
    category = context.user_data.get('new_template_category')

    if name and category:
        success = database.save_response_template(name, template_text, category)

        if success:
            await update.message.reply_text(
                f"✅ Шаблон '{name}' успешно создан!",
                reply_markup=get_admin_main_keyboard()
            )

            # Очищаем временные данные
            if 'new_template_name' in context.user_data:
                del context.user_data['new_template_name']
            if 'new_template_category' in context.user_data:
                del context.user_data['new_template_category']

            return ADMIN_MAIN
        else:
            await update.message.reply_text(
                "❌ Ошибка при создании шаблона. Попробуйте снова.",
                reply_markup=get_admin_main_keyboard()
            )
            return ADMIN_MAIN
    else:
        await update.message.reply_text(
            "❌ Ошибка: данные шаблона не найдены. Попробуйте снова.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN


async def admin_use_template(update: Update, context: CallbackContext):
    """Использование шаблона ответа"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith('admin_use_template_'):
        template_id = data.replace('admin_use_template_', '')
        order_id = context.user_data.get('current_order_id')

        # Получаем шаблон
        templates = database.get_response_templates()
        template = next((t for t in templates if str(t['id']) == template_id), None)

        if template and order_id:
            # Получаем информацию о заказе
            order = database.get_order_details(order_id)

            if order:
                # Заменяем плейсхолдеры в шаблоне
                message_text = template['text'].replace('{order_id}', order_id)

                # Отправляем сообщение студенту
                try:
                    await context.bot.send_message(
                        chat_id=order.get('user_id'),
                        text=f"📩 Сообщение от эксперта по заказу #{order_id}:\n\n{message_text}"
                    )

                    # Сохраняем сообщение в историю
                    database.save_message_to_history(order_id, "admin", message_text)

                    # Логируем действие
                    database.log_admin_action(update.effective_user.id, f"use_template_{template_id}", order_id)

                    await query.edit_message_text(
                        f"✅ Шаблон '{template['name']}' отправлен студенту @{order.get('username', 'Не указано')}.",
                        reply_markup=get_admin_order_actions_keyboard(order_id)
                    )

                except Exception as e:
                    logger.error(f"Ошибка отправки шаблона: {e}")
                    await query.edit_message_text(
                        "❌ Не удалось отправить сообщение студенту.",
                        reply_markup=get_admin_order_actions_keyboard(order_id)
                    )

                return ADMIN_ORDER_DETAILS

    await query.edit_message_text(
        "❌ Ошибка использования шаблона.",
        reply_markup=get_admin_order_actions_keyboard(order_id)
    )
    return ADMIN_ORDER_DETAILS


async def admin_force_set_price(update: Update, context: CallbackContext):
    """Принудительная установка цены для заказа"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('admin_force_set_price_', '')
    context.user_data['current_order_id'] = order_id

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if not order:
        await query.edit_message_text("Заказ не найден.")
        return ADMIN_VIEW_ORDERS

    await query.edit_message_text(
        f"💰 Принудительная установка цены для заказа #{order_id}\n\n"
        f"Текущий бюджет студента: {order.get('budget', 0)} руб.\n"
        f"Введите новую цену (минимальная цена: {Config.MIN_BUDGET} руб.):"
    )

    return ADMIN_SET_PRICE


async def admin_handle_force_price(update: Update, context: CallbackContext):
    """Обработка принудительной установки цены"""
    try:
        price_text = update.message.text
        order_id = context.user_data.get('current_order_id')

        if not order_id:
            await update.message.reply_text("Ошибка: не выбран заказ.")
            return ADMIN_MAIN

        try:
            price = float(price_text)
            if price < Config.MIN_BUDGET:
                await update.message.reply_text(
                    f"Цена не может быть меньше {Config.MIN_BUDGET} руб. Введите корректную цену:"
                )
                return ADMIN_SET_PRICE
        except ValueError:
            await update.message.reply_text("Неверный формат цены. Введите число:")
            return ADMIN_SET_PRICE

        # Обновляем цену в базе данных
        database.update_order_price(order_id, price)

        # Получаем информацию о заказе
        order = database.get_order_details(order_id)

        # Отправляем сообщение студенту
        student_message = (
            f"✅ Эксперт найден для вашего заказа #{order_id}!\n\n"
            f"Стоимость работ составляет: {price} руб.\n\n"
            f"Для продолжения необходимо подтвердить и оплатить заказ."
        )

        # Создаем клавиатуру для студента
        keyboard = get_student_confirmation_keyboard(order_id, price, order.get('user_id'))

        await context.bot.send_message(
            chat_id=order.get('user_id'),
            text=student_message,
            reply_markup=keyboard
        )

        # Логируем действие
        database.log_admin_action(update.effective_user.id, f"force_set_price_{price}", order_id)

        await update.message.reply_text(
            f"✅ Цена {price} руб. установлена для заказа #{order_id}. "
            f"Студент уведомлен и может подтвердить заказ.",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

        return ADMIN_ORDER_DETAILS

    except Exception as e:
        logger.error(f"Ошибка установки цены: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")
        return ADMIN_ORDER_DETAILS


async def admin_upload_work(update: Update, context: CallbackContext):
    """Начало загрузки выполненной работы"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('admin_upload_work_', '')
    context.user_data['current_order_id'] = order_id
    context.user_data['completed_files'] = []  # Инициализируем список для файлов

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if not order:
        await query.edit_message_text("Заказ не найден.")
        return ADMIN_VIEW_ORDERS

    await query.edit_message_text(
        f"📤 Загрузите файлы выполненной работы для заказа #{order_id}.\n\n"
        f"После загрузки всех файлов отправьте команду /done."
    )

    return ADMIN_UPLOAD_WORK


async def admin_handle_completed_file(update: Update, context: CallbackContext):
    """Обработка загрузки выполненного файла"""
    order_id = context.user_data.get('current_order_id')

    if not order_id:
        await update.message.reply_text("Ошибка: не выбран заказ.")
        return ADMIN_MAIN

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if not order:
        await update.message.reply_text("Заказ не найден.")
        return ADMIN_VIEW_ORDERS

    # Создаем папку для выполненной работы
    completed_folder = utils.create_order_folder(order_id, order.get('user_id'), "completed")

    if not completed_folder:
        await update.message.reply_text("Ошибка создания папки для файлов.")
        return ADMIN_UPLOAD_WORK

    # Сохраняем файл
    file = None
    file_path = None

    if update.message.document:
        file = update.message.document
    elif update.message.photo:
        file = update.message.photo[-1]  # Берем самое большое фото

    if file:
        file_path = await utils.save_file(file, completed_folder)

    if file_path:
        # Добавляем файл в список
        if 'completed_files' not in context.user_data:
            context.user_data['completed_files'] = []

        context.user_data['completed_files'].append(file_path)

        await update.message.reply_text(
            f"✅ Файл сохранен. Загружено файлов: {len(context.user_data['completed_files'])}\n\n"
            f"Продолжайте загрузку или отправьте /done для завершения."
        )
    else:
        await update.message.reply_text("❌ Не удалось сохранить файл. Попробуйте еще раз.")

    return ADMIN_UPLOAD_WORK


async def admin_finish_upload_work(update: Update, context: CallbackContext):
    """Завершение загрузки выполненных работ"""
    order_id = context.user_data.get('current_order_id')

    if not order_id:
        await update.message.reply_text("Ошибка: не выбран заказ.")
        return ADMIN_MAIN

    # Получаем список загруженных файлов
    completed_files = context.user_data.get('completed_files', [])

    if not completed_files:
        await update.message.reply_text("Не загружено ни одного файла.")
        return ADMIN_UPLOAD_WORK

    # Сохраняем информацию о файлах в базе
    database.update_order_completed_files(order_id, completed_files)

    # Обновляем статус заказа
    database.update_order_status(order_id, 'work_uploaded')

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    # Отправляем уведомление студенту
    student_message = (
        f"✅ Работа по вашему заказу #{order_id} готова!\n\n"
        f"Вы можете скачать файлы и проверить качество выполнения.\n\n"
        f"После проверки подтвердите принятие работы или запросите доработку."
    )

    from keyboards import get_work_approval_keyboard
    keyboard = get_work_approval_keyboard(order_id)

    await context.bot.send_message(
        chat_id=order.get('user_id'),
        text=student_message,
        reply_markup=keyboard
    )

    # Отправляем файлы студенту
    try:
        from utils import send_files_as_archive
        await send_files_as_archive(
            update,
            context,
            completed_files,
            f"Файлы по заказу #{order_id}"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки файлов студенту: {e}")

    # Логируем действие
    database.log_admin_action(update.effective_user.id, f"upload_work_{len(completed_files)}_files", order_id)

    await update.message.reply_text(
        f"✅ Работа по заказу #{order_id} отправлена студенту. Ожидается подтверждение.",
        reply_markup=get_admin_order_actions_keyboard(order_id)
    )

    # Очищаем временные данные
    if 'completed_files' in context.user_data:
        del context.user_data['completed_files']

    return ADMIN_ORDER_DETAILS


async def admin_complete_order(update: Update, context: CallbackContext):
    """Завершение заказа администратором"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('admin_complete_', '')

    # Обновляем статус заказа (теперь с записью времени завершения)
    database.update_order_status(order_id, 'completed')

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if order:
        # Отправляем уведомление студенту
        await context.bot.send_message(
            chat_id=order.get('user_id'),
            text=f"✅ Заказ #{order_id} завершен. Спасибо за сотрудничество!"
        )

    # Логируем действие
    database.log_admin_action(update.effective_user.id, f"complete_order", order_id)

    await query.edit_message_text(
        f"✅ Заказ #{order_id} завершен.",
        reply_markup=get_admin_order_actions_keyboard(order_id)
    )

    return ADMIN_ORDER_DETAILS


async def admin_delete_order_completely(update: Update, context: CallbackContext):
    """Полное удаление заказа со всеми данными"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('admin_delete_completely_', '')

    # Получаем информацию о заказе перед удалением
    order = database.get_order_details(order_id)

    if not order:
        await query.edit_message_text("Заказ не найден.")
        return ADMIN_VIEW_ORDERS

    # Удаляем файлы заказа
    user_id = order.get('user_id')

    # Удаляем папку с загруженными файлами
    upload_folder = utils.create_order_folder(order_id, user_id, "uploads")
    if upload_folder and upload_folder.exists():
        shutil.rmtree(upload_folder)

    # Удаляем папку с выполненной работой
    completed_folder = utils.create_order_folder(order_id, user_id, "completed")
    if completed_folder and completed_folder.exists():
        shutil.rmtree(completed_folder)

    # Удаляем запись из базы данных
    database.delete_order(order_id)

    # Логируем действие
    database.log_admin_action(update.effective_user.id, f"delete_order_completely", order_id)

    # Уведомляем студента
    try:
        await context.bot.send_message(
            chat_id=order.get('user_id'),
            text=f"❌ Ваш заказ #{order_id} был полностью удален администратором."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления студента: {e}")

    await query.edit_message_text(
        f"✅ Заказ #{order_id} полностью удален со всеми данными.",
        reply_markup=get_admin_main_keyboard()
    )

    return ADMIN_MAIN


async def admin_all_orders_navigation(update: Update, context: CallbackContext):
    """Навигация по всем заказам"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith('admin_all_orders_prev_'):
        new_page = int(data.replace('admin_all_orders_prev_', ''))
    elif data.startswith('admin_all_orders_next_'):
        new_page = int(data.replace('admin_all_orders_next_', ''))
    else:
        new_page = context.user_data.get('all_orders_page', 0)

    return await show_all_orders_page(update, context, new_page)


# Функции для работы с заказами по статусу
def get_orders_by_status(status):
    """Получение заказов по статусу"""
    try:
        conn = database.get_connection()
        c = conn.cursor()

        if status == "all":
            c.execute("SELECT * FROM orders ORDER BY created_at DESC")
        else:
            c.execute("SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC", (status,))

        orders = c.fetchall()
        return [dict(order) for order in orders]
    except Exception as e:
        logger.error(f"Ошибка получения заказов по статусу: {e}")
        return []
    finally:
        conn.close()