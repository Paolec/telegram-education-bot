import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from datetime import datetime

from config import Config
from database import (
    get_all_orders, get_order_details, update_order_price, update_order_status,
    update_order_completed_files, update_payment_url, delete_order,
    save_message_to_history, log_admin_action
)
from utils import create_order_folder, save_file, split_long_message, log_errors
from keyboards import (
    get_admin_main_keyboard, get_admin_order_actions_keyboard,
    get_admin_orders_navigation_keyboard, get_back_to_info_keyboard
)
from payment import generate_robokassa_payment_link

logger = logging.getLogger(__name__)

# Состояния разговора для админ-панели
ADMIN_MAIN, ADMIN_VIEW_ORDERS, ADMIN_ORDER_DETAILS = range(3)
ADMIN_SEND_MESSAGE, ADMIN_SET_PRICE, ADMIN_UPLOAD_WORK = range(3, 6)


@log_errors
async def admin_start(update: Update, context: CallbackContext):
    """Обработка команды /admin для администратора"""
    user = update.effective_user

    # Проверяем, является ли пользователь администратором
    if user.id != Config.ADMIN_ID:
        await update.message.reply_text("❌ У вас нет доступа к админ-панели.")
        return ConversationHandler.END

    welcome_text = (
        f"👋 Добро пожаловать в админ-панель, {user.first_name}!\n\n"
        "Здесь вы можете управлять заказами, общаться с пользователями "
        "и отслеживать статусы выполненных работ."
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_admin_main_keyboard()
    )

    # Логируем действие администратора
    log_admin_action(user.id, "вошел в админ-панель")

    return ADMIN_MAIN


@log_errors
async def admin_start_from_query(update: Update, context: CallbackContext):
    """Обработка возврата в главное меню админ-панели из callback"""
    query = update.callback_query
    await query.answer()

    user = query.from_user

    welcome_text = (
        f"👋 Добро пожаловать в админ-панель, {user.first_name}!\n\n"
        "Здесь вы можете управлять заказами, общаться с пользователями "
        "и отслеживать статусы выполненных работ."
    )

    await query.edit_message_text(
        welcome_text,
        reply_markup=get_admin_main_keyboard()
    )

    return ADMIN_MAIN


@log_errors
async def admin_cancel(update: Update, context: CallbackContext):
    """Обработка команды отмены в админ-панели"""
    user = update.effective_user
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Действие в админ-панели отменено. Используйте /admin для возврата.",
        reply_markup=get_admin_main_keyboard()
    )

    return ADMIN_MAIN


@log_errors
async def admin_view_orders(update: Update, context: CallbackContext):
    """Просмотр списка заказов"""
    query = update.callback_query
    await query.answer()

    # Получаем все заказы
    orders = get_all_orders()

    if not orders:
        await query.edit_message_text(
            "📋 Заказов пока нет.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Сохраняем заказы в контексте для навигации
    context.user_data['all_orders'] = orders
    context.user_data['current_page'] = 0
    context.user_data['current_status'] = 'all'

    # Формируем текст для отображения
    orders_text = f"📋 Все заказы ({len(orders)}):\n\n"

    # Показываем первые 5 заказов
    for i, order in enumerate(orders[:5], 1):
        status_emoji = {
            'new': '🔍',
            'in_progress': '🛠',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order['status'], '❓')

        orders_text += (
            f"{i}. #{order['order_id']} - {status_emoji} {Config.ORDER_STATUSES.get(order['status'], order['status'])}\n"
            f"   👤 {order.get('username', 'Неизвестно')}\n"
            f"   📚 {order.get('discipline', 'Не указано')}\n"
            f"   📅 {order.get('deadline', 'Не указано')}\n\n"
        )

    # Добавляем навигацию, если заказов больше 5
    total_pages = (len(orders) + 4) // 5  # Округление вверх

    await query.edit_message_text(
        orders_text,
        reply_markup=get_admin_orders_navigation_keyboard('all', 0, total_pages)
    )

    return ADMIN_VIEW_ORDERS


@log_errors
async def admin_orders_by_status(update: Update, context: CallbackContext):
    """Фильтрация заказов по статусу"""
    query = update.callback_query
    await query.answer()

    status = query.data.replace("admin_orders_", "")

    # Получаем все заказы
    all_orders = get_all_orders()

    # Фильтруем заказы по статусу
    if status == 'all':
        filtered_orders = all_orders
        status_text = "все"
    else:
        filtered_orders = [order for order in all_orders if order['status'] == status]
        status_text = Config.ORDER_STATUSES.get(status, status)

    if not filtered_orders:
        await query.edit_message_text(
            f"📋 Заказов со статусом '{status_text}' нет.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Сохраняем заказы в контексте для навигации
    context.user_data['all_orders'] = filtered_orders
    context.user_data['current_page'] = 0
    context.user_data['current_status'] = status

    # Формируем текст для отображения
    orders_text = f"📋 Заказы ({status_text}): {len(filtered_orders)}\n\n"

    # Показываем первые 5 заказов
    for i, order in enumerate(filtered_orders[:5], 1):
        status_emoji = {
            'new': '🔍',
            'in_progress': '🛠',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order['status'], '❓')

        orders_text += (
            f"{i}. #{order['order_id']} - {status_emoji} {Config.ORDER_STATUSES.get(order['status'], order['status'])}\n"
            f"   👤 {order.get('username', 'Неизвестно')}\n"
            f"   📚 {order.get('discipline', 'Не указано')}\n"
            f"   📅 {order.get('deadline', 'Не указано')}\n\n"
        )

    # Добавляем навигацию, если заказов больше 5
    total_pages = (len(filtered_orders) + 4) // 5  # Округление вверх

    await query.edit_message_text(
        orders_text,
        reply_markup=get_admin_orders_navigation_keyboard(status, 0, total_pages)
    )

    return ADMIN_VIEW_ORDERS


@log_errors
async def admin_handle_orders_navigation(update: Update, context: CallbackContext):
    """Обработка навигации по страницам заказов"""
    query = update.callback_query
    await query.answer()

    # Извлекаем параметры из callback_data
    parts = query.data.split('_')
    direction = parts[2]  # prev или next
    status = parts[3]  # статус заказов
    page = int(parts[4])  # номер страницы

    # Получаем отфильтрованные заказы из контекста
    filtered_orders = context.user_data.get('all_orders', [])

    if not filtered_orders:
        await query.edit_message_text(
            "❌ Нет заказов для отображения.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Обновляем текущую страницу в контексте
    context.user_data['current_page'] = page
    context.user_data['current_status'] = status

    # Формируем текст для отображения
    status_text = "все" if status == 'all' else Config.ORDER_STATUSES.get(status, status)
    orders_text = f"📋 Заказы ({status_text}): {len(filtered_orders)}\n\n"

    # Вычисляем индексы заказов для текущей страницы
    start_idx = page * 5
    end_idx = min(start_idx + 5, len(filtered_orders))

    # Показываем заказы для текущей страницы
    for i, order in enumerate(filtered_orders[start_idx:end_idx], start_idx + 1):
        status_emoji = {
            'new': '🔍',
            'in_progress': '🛠',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order['status'], '❓')

        orders_text += (
            f"{i}. #{order['order_id']} - {status_emoji} {Config.ORDER_STATUSES.get(order['status'], order['status'])}\n"
            f"   👤 {order.get('username', 'Неизвестно')}\n"
            f"   📚 {order.get('discipline', 'Не указано')}\n"
            f"   📅 {order.get('deadline', 'Не указано')}\n\n"
        )

    # Добавляем навигацию
    total_pages = (len(filtered_orders) + 4) // 5  # Округление вверх

    await query.edit_message_text(
        orders_text,
        reply_markup=get_admin_orders_navigation_keyboard(status, page, total_pages)
    )

    return ADMIN_VIEW_ORDERS


@log_errors
async def admin_order_details(update: Update, context: CallbackContext):
    """Просмотр деталей конкретного заказа"""
    query = update.callback_query
    await query.answer()

    # Извлекаем ID заказа из callback_data
    order_id = query.data.replace("admin_order_", "")

    # Получаем детали заказа
    order_details = get_order_details(order_id)

    if not order_details:
        await query.edit_message_text(
            f"❌ Заказ #{order_id} не найден.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Формируем текст с деталями заказа
    order_text = (
        f"📋 Детали заказа #{order_id}\n\n"
        f"👤 Пользователь: {order_details.get('username', 'Неизвестно')} (ID: {order_details['user_id']})\n"
        f"📚 Дисциплина: {order_details.get('discipline', 'Не указано')}\n"
        f"📋 Тип работы: {order_details.get('work_type', 'Не указано')}\n"
        f"📅 Дедлайн: {order_details.get('deadline', 'Не указано')}\n"
        f"💰 Бюджет: {order_details.get('budget', 0)} руб.\n"
        f"💵 Итоговая сумма: {order_details.get('final_amount', 0)} руб.\n"
        f"📊 Статус: {Config.ORDER_STATUSES.get(order_details.get('status', 'new'), order_details.get('status', 'new'))}\n"
        f"💳 Статус оплаты: {'✅ Оплачен' if order_details.get('payment_status') == 'paid' else '❌ Не оплачен'}\n"
    )

    if order_details.get('plagiarism_required', 0) == 1:
        order_text += (
            f"🔍 Антиплагиат: {order_details.get('plagiarism_system', 'Не указано')}\n"
            f"📊 Требуемый процент: {order_details.get('plagiarism_percent', 0)}%\n"
        )

    if order_details.get('description'):
        order_text += f"📝 Описание: {order_details['description']}\n"

    if order_details.get('files'):
        order_text += f"📎 Файлы: {order_details['files']}\n"

    if order_details.get('expert_name'):
        order_text += f"👨‍💻 Исполнитель: {order_details['expert_name']}\n"

    if order_details.get('completed_files'):
        order_text += f"✅ Выполненные файлы: {order_details['completed_files']}\n"

    order_text += f"\n📅 Создан: {order_details.get('created_at', 'Неизвестно')}"

    # Сохраняем ID заказа в контексте для последующих действий
    context.user_data['current_order_id'] = order_id

    # Логируем действие администратора
    log_admin_action(query.from_user.id, f"просмотрел детали заказа {order_id}")

    await query.edit_message_text(
        order_text,
        reply_markup=get_admin_order_actions_keyboard(order_id)
    )

    return ADMIN_ORDER_DETAILS


@log_errors
async def admin_send_message(update: Update, context: CallbackContext):
    """Начало процесса отправки сообщения пользователю"""
    query = update.callback_query
    await query.answer()

    # Извлекаем ID заказа из callback_data
    order_id = query.data.replace("admin_send_msg_", "")

    # Сохраняем ID заказа в контексте
    context.user_data['current_order_id'] = order_id

    await query.edit_message_text(
        f"💬 Введите сообщение для пользователя (заказ #{order_id}):"
    )

    return ADMIN_SEND_MESSAGE


@log_errors
async def admin_handle_message(update: Update, context: CallbackContext):
    """Обработка ввода и отправка сообщения пользователю"""
    message_text = update.message.text
    order_id = context.user_data.get('current_order_id')

    if not order_id:
        await update.message.reply_text(
            "❌ Ошибка: не найден ID заказа.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Получаем детали заказа
    order_details = get_order_details(order_id)

    if not order_details:
        await update.message.reply_text(
            f"❌ Заказ #{order_id} не найден.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Отправляем сообщение пользователю
    try:
        user_message = (
            f"📩 Сообщение от администратора по заказу #{order_id}:\n\n"
            f"{message_text}\n\n"
            f"Для ответа свяжитесь с администратором."
        )

        await context.bot.send_message(
            chat_id=order_details['user_id'],
            text=user_message
        )

        # Сохраняем сообщение в историю
        save_message_to_history(order_id, "admin", message_text)

        # Логируем действие администратора
        log_admin_action(update.effective_user.id, f"отправил сообщение по заказу {order_id}")

        await update.message.reply_text(
            f"✅ Сообщение отправлено пользователю (заказ #{order_id}).",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю: {e}")
        await update.message.reply_text(
            f"❌ Не удалось отправить сообщение пользователю: {e}",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    return ADMIN_ORDER_DETAILS


@log_errors
async def admin_set_price(update: Update, context: CallbackContext):
    """Начало процесса установки цены заказа"""
    query = update.callback_query
    await query.answer()

    # Извлекаем ID заказа из callback_data
    order_id = query.data.replace("admin_set_price_", "")

    # Сохраняем ID заказа в контексте
    context.user_data['current_order_id'] = order_id

    # Получаем детали заказа
    order_details = get_order_details(order_id)

    if not order_details:
        await query.edit_message_text(
            f"❌ Заказ #{order_id} не найден.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    budget = order_details.get('budget', 0)

    await query.edit_message_text(
        f"💰 Текущий бюджет заказа: {budget} руб.\n\n"
        f"Введите итоговую стоимость заказа #{order_id} в рублях:"
    )

    return ADMIN_SET_PRICE


@log_errors
async def admin_handle_price(update: Update, context: CallbackContext):
    """Обработка ввода и установка цены заказа"""
    try:
        price = float(update.message.text)

        if price <= 0:
            await update.message.reply_text(
                "❌ Цена должна быть положительным числом. Попробуйте еще раз:"
            )
            return ADMIN_SET_PRICE

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат цены. Введите число:"
        )
        return ADMIN_SET_PRICE

    order_id = context.user_data.get('current_order_id')

    if not order_id:
        await update.message.reply_text(
            "❌ Ошибка: не найден ID заказа.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Обновляем цену заказа
    update_order_price(order_id, price)

    # Генерируем платежную ссылку
    order_details = get_order_details(order_id)
    payment_url = generate_robokassa_payment_link(
        order_id=order_id,
        amount=price,
        description=f"{order_details['work_type']} по {order_details['discipline']}",
        user_id=order_details['user_id']
    )

    # Сохраняем платежную ссылку в БД
    update_payment_url(order_id, payment_url)

    # Отправляем сообщение пользователю
    try:
        user_message = (
            f"💰 Для вашего заказа #{order_id} установлена цена: {price} руб.\n\n"
            f"Для оплаты перейдите по ссылке: {payment_url}\n\n"
            "После оплаты работа будет запущена в выполнение."
        )

        await context.bot.send_message(
            chat_id=order_details['user_id'],
            text=user_message
        )

        # Логируем действие администратора
        log_admin_action(update.effective_user.id, f"установил цену {price} руб. для заказа {order_id}")

        await update.message.reply_text(
            f"✅ Цена заказа #{order_id} установлена: {price} руб.\n\n"
            f"Платежная ссылка отправлена пользователю.",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю: {e}")
        await update.message.reply_text(
            f"✅ Цена заказа #{order_id} установлена: {price} руб.\n\n"
            f"❌ Не удалось отправить сообщение пользователю: {e}",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    return ADMIN_ORDER_DETAILS


@log_errors
async def admin_upload_work(update: Update, context: CallbackContext):
    """Начало процесса загрузки выполненной работы"""
    query = update.callback_query
    await query.answer()

    # Извлекаем ID заказа из callback_data
    order_id = query.data.replace("admin_upload_work_", "")

    # Сохраняем ID заказа в контексте
    context.user_data['current_order_id'] = order_id
    context.user_data['completed_files'] = []

    await query.edit_message_text(
        f"📤 Загрузите файлы выполненной работы для заказа #{order_id}.\n\n"
        "После загрузки всех файлов используйте команду /done для завершения."
    )

    return ADMIN_UPLOAD_WORK


@log_errors
async def admin_handle_completed_file(update: Update, context: CallbackContext):
    """Обработка загрузки файлов выполненной работы"""
    order_id = context.user_data.get('current_order_id')

    if not order_id:
        await update.message.reply_text(
            "❌ Ошибка: не найден ID заказа.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Создаем папку для выполненной работы
    order_details = get_order_details(order_id)
    order_folder = create_order_folder(order_id, order_details['user_id'], "completed")

    if not order_folder:
        await update.message.reply_text(
            "❌ Ошибка создания папки для выполненной работы.",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )
        return ADMIN_ORDER_DETAILS

    # Сохраняем файл
    if update.message.document:
        file = update.message.document
    elif update.message.photo:
        file = update.message.photo[-1]  # Берем самое качественное фото
    else:
        await update.message.reply_text(
            "❌ Формат файла не поддерживается. Используйте документы или изображения."
        )
        return ADMIN_UPLOAD_WORK

    # Проверяем размер файла
    if file.file_size > Config.MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ Файл слишком большой. Максимальный размер: {Config.MAX_FILE_SIZE // 1024 // 1024}MB."
        )
        return ADMIN_UPLOAD_WORK

    # Сохраняем файл
    file_path = await save_file(file, order_folder)

    if file_path:
        if 'completed_files' not in context.user_data:
            context.user_data['completed_files'] = []
        context.user_data['completed_files'].append(file_path)

        await update.message.reply_text(
            f"✅ Файл сохранен. Загружено файлов: {len(context.user_data['completed_files'])}\n\n"
            "Продолжайте загрузку или используйте /done для завершения."
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при сохранении файла. Попробуйте еще раз."
        )

    return ADMIN_UPLOAD_WORK


@log_errors
async def admin_finish_upload_work(update: Update, context: CallbackContext):
    """Завершение загрузки выполненной работы"""
    order_id = context.user_data.get('current_order_id')

    if not order_id:
        await update.message.reply_text(
            "❌ Ошибка: не найден ID заказа.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN

    # Обновляем список выполненных файлов в БД
    completed_files = context.user_data.get('completed_files', [])
    update_order_completed_files(order_id, completed_files)

    # Отправляем уведомление пользователю
    order_details = get_order_details(order_id)

    try:
        user_message = (
            f"✅ Ваш заказ #{order_id} выполнен!\n\n"
            f"Загружено файлов: {len(completed_files)}\n\n"
            f"Пожалуйста, проверьте работу и подтвердите получение."
        )

        # Создаем клавиатуру для подтверждения
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить получение", callback_data=f"student_approve_{order_id}")],
            [InlineKeyboardButton("❌ Отклонить работу", callback_data=f"student_reject_{order_id}")]
        ])

        await context.bot.send_message(
            chat_id=order_details['user_id'],
            text=user_message,
            reply_markup=confirm_keyboard
        )

        # Логируем действие администратора
        log_admin_action(update.effective_user.id, f"загрузил выполненную работу для заказа {order_id}")

        await update.message.reply_text(
            f"✅ Работа по заказу #{order_id} загружена и отправлена пользователю.",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю: {e}")
        await update.message.reply_text(
            f"✅ Работа по заказу #{order_id} загружена.\n\n"
            f"❌ Не удалось отправить уведомление пользователю: {e}",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    # Очищаем список файлов из контекста
    if 'completed_files' in context.user_data:
        del context.user_data['completed_files']

    return ADMIN_ORDER_DETAILS


@log_errors
async def admin_complete_order(update: Update, context: CallbackContext):
    """Подтверждение выполнения заказа"""
    query = update.callback_query
    await query.answer()

    # Извлекаем ID заказа из callback_data
    order_id = query.data.replace("admin_complete_", "")

    # Обновляем статус заказа
    update_order_status(order_id, "completed")

    # Отправляем уведомление пользователю
    order_details = get_order_details(order_id)

    try:
        user_message = (
            f"✅ Ваш заказ #{order_id} выполнен и завершен!\n\n"
            f"Спасибо за сотрудничество! Если у вас возникнут вопросы, обращайтесь к администратору."
        )

        await context.bot.send_message(
            chat_id=order_details['user_id'],
            text=user_message
        )

        # Логируем действие администратора
        log_admin_action(query.from_user.id, f"завершил заказ {order_id}")

        await query.edit_message_text(
            f"✅ Заказ #{order_id} завершен.",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю: {e}")
        await query.edit_message_text(
            f"✅ Заказ #{order_id} завершен.\n\n"
            f"❌ Не удалось отправить уведомление пользователю: {e}",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    return ADMIN_ORDER_DETAILS


@log_errors
async def admin_cancel_order(update: Update, context: CallbackContext):
    """Отмена заказа"""
    query = update.callback_query
    await query.answer()

    # Извлекаем ID заказа из callback_data
    order_id = query.data.replace("admin_cancel_", "")

    # Обновляем статус заказа
    update_order_status(order_id, "cancelled")

    # Отправляем уведомление пользователю
    order_details = get_order_details(order_id)

    try:
        user_message = (
            f"❌ Ваш заказ #{order_id} отменен администратором.\n\n"
            f"Если у вас возникли вопросы, пожалуйста, свяжитесь с администратором для выяснения причин."
        )

        await context.bot.send_message(
            chat_id=order_details['user_id'],
            text=user_message
        )

        # Логируем действие администратора
        log_admin_action(query.from_user.id, f"отменил заказ {order_id}")

        await query.edit_message_text(
            f"✅ Заказ #{order_id} отменен.",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю: {e}")
        await query.edit_message_text(
            f"✅ Заказ #{order_id} отменен.\n\n"
            f"❌ Не удалось отправить уведомление пользователю: {e}",
            reply_markup=get_admin_order_actions_keyboard(order_id)
        )

    return ADMIN_ORDER_DETAILS


@log_errors
async def handle_wrong_input(update: Update, context: CallbackContext):
    """Обработка неправильного ввода в админ-панели"""
    await update.message.reply_text("Пожалуйста, введите текстовое сообщение.")
    return context.user_data.get('current_state', ADMIN_MAIN)