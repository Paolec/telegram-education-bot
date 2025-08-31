# user_handlers.py - обработчики для пользовательской части бота
import logging
import shutil
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from config import Config
import database
import utils
from keyboards import (
    get_disciplines_keyboard, get_work_types_keyboard, get_plagiarism_systems_keyboard,
    get_budget_type_keyboard, get_plagiarism_required_keyboard, get_upload_done_keyboard,
    get_skip_description_keyboard, get_user_main_keyboard, get_info_keyboard,
    get_back_to_info_keyboard, get_payment_confirmation_keyboard,
    get_student_confirmation_keyboard, get_payment_keyboard, get_work_approval_keyboard,
    get_orders_list_keyboard, get_order_details_keyboard
)

logger = logging.getLogger(__name__)

# Состояния разговора для пользователя
(
    USER_SELECTING_ACTION, USER_CHOOSE_DISCIPLINE, USER_CHOOSE_WORK_TYPE, USER_SET_CUSTOM_WORK_TYPE,
    USER_SET_DEADLINE, USER_SELECT_BUDGET_TYPE, USER_SET_BUDGET, USER_SET_PLAGIARISM_REQUIRED,
    USER_CHOOSING_PLAGIARISM_SYSTEM, USER_SET_PLAGIARISM_PERCENT, USER_UPLOAD_FILES,
    USER_SET_DESCRIPTION, USER_VIEWING_ORDERS, USER_INFO_MENU, USER_ORDER_DETAILS
) = range(15)


async def user_start(update: Update, context: CallbackContext):
    """Начало работы с ботом для пользователя"""
    # Определяем, откуда пришел запрос - из сообщения или callback query
    if update.message:
        user = update.effective_user
        message = update.message
    elif update.callback_query:
        user = update.callback_query.from_user
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        logger.error("Неизвестный тип update")
        return ConversationHandler.END

    user_id = user.id
    username = user.username or user.first_name or "Пользователь"

    # Сохраняем информацию о пользователе в контексте
    context.user_data['user_id'] = user_id
    context.user_data['username'] = username

    # Очищаем данные предыдущего заказа, если они есть
    if 'order_data' in context.user_data:
        del context.user_data['order_data']

    await message.reply_text(
        f"👋 Привет, {username}!\n\n"
        "Я — StudHelpBot, твой надежный помощник в учебном деле! 🎓\n\n"
        "С моей помощью ты сможешь:\n"
        "✅ Заказать работу любой сложности со сроком от 1 часа!\n"
        "✅ Получить помощь от опытных специалистов\n"
        "✅ Гарантированное качество и оригинальность!\n\n"
        "Доверься профессионалам! Выбери действие:",
        reply_markup=get_user_main_keyboard()
    )

    return USER_SELECTING_ACTION


async def user_cancel(update: Update, context: CallbackContext):
    """Отмена действия пользователем"""
    # Очищаем данные заказа
    if 'order_data' in context.user_data:
        del context.user_data['order_data']

    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=get_user_main_keyboard()
    )

    return USER_SELECTING_ACTION


async def user_create_order(update: Update, context: CallbackContext):
    """Начало создания заказа"""
    query = update.callback_query
    await query.answer()

    user_id = context.user_data.get('user_id')

    # Проверяем количество активных заказов
    active_orders_count = database.get_user_active_orders_count(user_id)
    if active_orders_count >= Config.MAX_ACTIVE_ORDERS:
        await query.edit_message_text(
            f"❌ У вас уже {active_orders_count} активных заказов. "
            f"Максимальное количество одновременно активных заказов: {Config.MAX_ACTIVE_ORDERS}.\n\n"
            "Дождитесь завершения текущих заказов или отмените один из них.",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    # Инициализируем данные заказа
    context.user_data['order_data'] = {
        'user_id': user_id,
        'username': context.user_data.get('username'),
        'order_id': utils.generate_order_id(user_id)
    }

    await query.edit_message_text(
        "📚 Выберите дисциплину:",
        reply_markup=get_disciplines_keyboard()
    )

    return USER_CHOOSE_DISCIPLINE


async def user_choose_discipline(update: Update, context: CallbackContext):
    """Обработка выбора дисциплины"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "user_back_to_start":
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    # Извлекаем ID дисциплины
    discipline_id = data.replace("user_disc_", "")

    # Сохраняем выбранную дисциплину
    discipline_name = next((name for id, name in Config.DISCIPLINES if id == discipline_id), "Неизвестная дисциплина")
    context.user_data['order_data']['discipline'] = discipline_name

    await query.edit_message_text(
        f"📚 Дисциплина: {discipline_name}\n\n"
        "📝 Выберите тип работы:",
        reply_markup=get_work_types_keyboard()
    )

    return USER_CHOOSE_WORK_TYPE


async def user_choose_work_type(update: Update, context: CallbackContext):
    """Обработка выбора типа работы"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "user_back_to_disciplines":
        await query.edit_message_text(
            "📚 Выберите дисциплину:",
            reply_markup=get_disciplines_keyboard()
        )
        return USER_CHOOSE_DISCIPLINE

    # Извлекаем ID типа работы
    work_type_id = data.replace("user_work_", "")

    if work_type_id == "other":
        # Запрос на ввод кастомного типа работы
        await query.edit_message_text(
            "✍️ Введите тип работы (например, 'Курсовой проект', 'Дипломная работа' и т.д.):"
        )
        return USER_SET_CUSTOM_WORK_TYPE

    # Сохраняем выбранный тип работы
    work_type_name = next((name for id, name in Config.WORK_TYPES if id == work_type_id), "Неизвестный тип работы")
    context.user_data['order_data']['work_type'] = work_type_name

    await query.edit_message_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {work_type_name}\n\n"
        "📅 Укажите дедлайн в формате ДД.ММ.ГГГГ (например, 25.08.2025):"
    )

    return USER_SET_DEADLINE


async def user_set_custom_work_type(update: Update, context: CallbackContext):
    """Обработка ввода кастомного типа работы"""
    custom_work_type = update.message.text

    if len(custom_work_type) > 100:
        await update.message.reply_text(
            "Название типа работы слишком длинное. Укажите более короткое название:"
        )
        return USER_SET_CUSTOM_WORK_TYPE

    # Сохраняем кастомный тип работы
    context.user_data['order_data']['work_type'] = custom_work_type

    await update.message.reply_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {custom_work_type}\n\n"
        "📅 Укажите дедлайн в формате ДД.ММ.ГГГГ (например, 25.08.2025):"
    )

    return USER_SET_DEADLINE


async def user_handle_deadline(update: Update, context: CallbackContext):
    """Обработка ввода дедлайна"""
    deadline_str = update.message.text

    # Проверяем корректность дедлайна
    is_valid, result = utils.validate_deadline(deadline_str)

    if not is_valid:
        await update.message.reply_text(result)
        return USER_SET_DEADLINE

    # Сохраняем дедлайн
    context.user_data['order_data']['deadline'] = deadline_str

    await update.message.reply_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
        f"📅 Дедлайн: {deadline_str}\n\n"
        "💰 Выберите способ определения бюджета:",
        reply_markup=get_budget_type_keyboard()
    )

    return USER_SELECT_BUDGET_TYPE


async def user_handle_budget_type(update: Update, context: CallbackContext):
    """Обработка выбора типа бюджета"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "user_expert_budget":
        # Пропускаем ввод бюджета, переходим к антиплагиату
        context.user_data['order_data']['budget'] = 0  # 0 означает, что цену назначит эксперт

        await query.edit_message_text(
            f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
            f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
            f"📅 Дедлайн: {context.user_data['order_data']['deadline']}\n"
            f"💰 Бюджет: Цену назначит эксперт\n\n"
            "🔍 Требуется ли проверка на антиплагиат?",
            reply_markup=get_plagiarism_required_keyboard()
        )

        return USER_SET_PLAGIARISM_REQUIRED

    # Запрос на ввод бюджета
    await query.edit_message_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
        f"📅 Дедлайн: {context.user_data['order_data']['deadline']}\n\n"
        f"💰 Укажите ваш бюджет (минимальная сумма: {Config.MIN_BUDGET} руб.):"
    )

    return USER_SET_BUDGET


async def user_handle_budget(update: Update, context: CallbackContext):
    """Обработка ввода бюджета"""
    budget_str = update.message.text

    # Проверяем корректность бюджета
    is_valid, result = utils.validate_budget(budget_str)

    if not is_valid:
        await update.message.reply_text(result)
        return USER_SET_BUDGET

    # Сохраняем бюджет
    context.user_data['order_data']['budget'] = result

    await update.message.reply_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
        f"📅 Дедлайн: {context.user_data['order_data']['deadline']}\n"
        f"💰 Бюджет: {result} руб.\n\n"
        "🔍 Требуется ли проверка на антиплагиат?",
        reply_markup=get_plagiarism_required_keyboard()
    )

    return USER_SET_PLAGIARISM_REQUIRED


async def user_handle_plagiarism_required(update: Update, context: CallbackContext):
    """Обработка необходимости антиплагиата"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "user_plagiarism_no":
        # Антиплагиат не требуется
        context.user_data['order_data']['plagiarism_required'] = False

        await query.edit_message_text(
            f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
            f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
            f"📅 Дедлайн: {context.user_data['order_data']['deadline']}\n"
            f"💰 Бюджет: {context.user_data['order_data']['budget']} руб.\n"
            f"🔍 Антиплагиат: Не требуется\n\n"
            "📎 Загрузите файлы с заданием (если есть) или нажмите 'Завершить загрузку':",
            reply_markup=get_upload_done_keyboard()
        )

        # Создаем папку для файлов заказа
        order_id = context.user_data['order_data']['order_id']
        user_id = context.user_data['order_data']['user_id']
        order_folder = utils.create_order_folder(order_id, user_id)

        if order_folder:
            context.user_data['order_data']['files_folder'] = str(order_folder)
            context.user_data['order_data']['files'] = []

        return USER_UPLOAD_FILES

    # Антиплагиат требуется
    context.user_data['order_data']['plagiarism_required'] = True

    await query.edit_message_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
        f"📅 Дедлайн: {context.user_data['order_data']['deadline']}\n"
        f"💰 Бюджет: {context.user_data['order_data']['budget']} руб.\n"
        f"🔍 Антиплагиат: Требуется\n\n"
        "Выберите систему проверки:",
        reply_markup=get_plagiarism_systems_keyboard()
    )

    return USER_CHOOSING_PLAGIARISM_SYSTEM


async def user_handle_plagiarism_system(update: Update, context: CallbackContext):
    """Обработка выбора системы антиплагиата"""
    query = update.callback_query
    await query.answer()

    data = query.data
    system_id = data.replace("user_plag_sys_", "")

    # Сохраняем выбранную систему
    system_data = Config.PLAGIARISM_SYSTEMS.get(system_id, {})
    context.user_data['order_data']['plagiarism_system'] = system_id
    context.user_data['order_data']['plagiarism_system_name'] = system_data.get('name', 'Неизвестная система')

    await query.edit_message_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
        f"📅 Дедлайн: {context.user_data['order_data']['deadline']}\n"
        f"💰 Бюджет: {context.user_data['order_data']['budget']} руб.\n"
        f"🔍 Антиплагиат: {system_data.get('name', 'Неизвестная система')}\n\n"
        "📊 Укажите требуемый процент оригинальности (0-100):"
    )

    return USER_SET_PLAGIARISM_PERCENT


async def user_handle_plagiarism_percent(update: Update, context: CallbackContext):
    """Обработка ввода процента антиплагиата"""
    percent_str = update.message.text

    # Проверяем корректность процента
    is_valid, result = utils.validate_plagiarism_percent(percent_str)

    if not is_valid:
        await update.message.reply_text(result)
        return USER_SET_PLAGIARISM_PERCENT

    # Сохраняем процент
    context.user_data['order_data']['plagiarism_percent'] = result

    await update.message.reply_text(
        f"📚 Дисциплина: {context.user_data['order_data']['discipline']}\n"
        f"📝 Тип работы: {context.user_data['order_data']['work_type']}\n"
        f"📅 Дедлайн: {context.user_data['order_data']['deadline']}\n"
        f"💰 Бюджет: {context.user_data['order_data']['budget']} руб.\n"
        f"🔍 Антиплагиат: {context.user_data['order_data']['plagiarism_system_name']}\n"
        f"📊 Требуемый процент: {result}%\n\n"
        "📎 Загрузите файлы с заданием (если есть) или нажмите 'Завершить загрузку':",
        reply_markup=get_upload_done_keyboard()
    )

    # Создаем папку для файлов заказа
    order_id = context.user_data['order_data']['order_id']
    user_id = context.user_data['order_data']['user_id']
    order_folder = utils.create_order_folder(order_id, user_id)

    if order_folder:
        context.user_data['order_data']['files_folder'] = str(order_folder)
        context.user_data['order_data']['files'] = []

    return USER_UPLOAD_FILES


async def user_handle_files(update: Update, context: CallbackContext):
    """Обработка загрузки файлов"""
    order_data = context.user_data.get('order_data', {})

    if not order_data or 'files_folder' not in order_data:
        await update.message.reply_text("Ошибка: данные заказа не найдены. Начните заново.")
        return USER_SELECTING_ACTION

    # Сохраняем файл
    file = None
    file_path = None

    if update.message.document:
        file = update.message.document
    elif update.message.photo:
        file = update.message.photo[-1]  # Берем самое большое фото

    if file:
        file_path = await utils.save_file(file, Path(order_data['files_folder']))

    if file_path:
        # Добавляем файл в список
        if 'files' not in order_data:
            order_data['files'] = []

        order_data['files'].append(file_path)
        context.user_data['order_data'] = order_data

        await update.message.reply_text(
            f"✅ Файл сохранен. Загружено файлов: {len(order_data['files'])}\n\n"
            f"Продолжайте загрузку или нажмите 'Завершить загрузку':",
            reply_markup=get_upload_done_keyboard()
        )
    else:
        await update.message.reply_text("❌ Не удалось сохранить файл. Попробуйте еще раз.")

    return USER_UPLOAD_FILES


async def user_handle_upload_done(update: Update, context: CallbackContext):
    """Завершение загрузки файлов"""
    query = update.callback_query
    await query.answer()

    order_data = context.user_data.get('order_data', {})

    if not order_data:
        await query.edit_message_text("Ошибка: данные заказа не найдены. Начните заново.")
        return USER_SELECTING_ACTION

    await query.edit_message_text(
        f"📚 Дисциплина: {order_data['discipline']}\n"
        f"📝 Тип работы: {order_data['work_type']}\n"
        f"📅 Дедлайн: {order_data['deadline']}\n"
        f"💰 Бюджет: {order_data['budget']} руб.\n"
        f"🔍 Антиплагиат: {order_data.get('plagiarism_system_name', 'Не требуется')}\n"
        f"📊 Требуемый процент: {order_data.get('plagiarism_percent', '0')}%\n"
        f"📎 Файлов загружено: {len(order_data.get('files', []))}\n\n"
        "✍️ Добавьте описание к заказу (или нажмите 'Пропустить описание'):",
        reply_markup=get_skip_description_keyboard()
    )

    return USER_SET_DESCRIPTION


async def user_handle_description(update: Update, context: CallbackContext):
    """Обработка ввода описания"""
    description = update.message.text

    if len(description) > 1000:
        await update.message.reply_text("Описание слишком длинное. Укоротите его до 1000 символов:")
        return USER_SET_DESCRIPTION

    # Сохраняем описание
    context.user_data['order_data']['description'] = description

    # Завершаем создание заказа
    return await finish_order_creation(update, context)


async def user_skip_description(update: Update, context: CallbackContext):
    """Пропуск описания"""
    query = update.callback_query
    await query.answer()

    # Завершаем создание заказа без описания
    context.user_data['order_data']['description'] = ""

    return await finish_order_creation(update, context)


async def finish_order_creation(update: Update, context: CallbackContext):
    """Завершение создания заказа"""
    order_data = context.user_data.get('order_data', {})

    if not order_data:
        # Используем правильный способ отправки сообщения в зависимости от типа update
        if update.message:
            await update.message.reply_text("Ошибка: данные заказа не найдены. Начните заново.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Ошибка: данные заказа не найдены. Начните заново.")
        else:
            logger.error("Неизвестный тип update в finish_order_creation")
        return USER_SELECTING_ACTION

    # Сохраняем заказ в базу данных
    order_id = database.save_order_to_db(order_data)

    if not order_id:
        if update.message:
            await update.message.reply_text("❌ Ошибка при создании заказа. Попробуйте позже.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("❌ Ошибка при создании заказа. Попробуйте позже.")
        return USER_SELECTING_ACTION

    # Формируем сообщение о создании заказа
    message = (
        f"✅ Заказ #{order_id} создан!\n\n"
        f"📚 Дисциплина: {order_data['discipline']}\n"
        f"📝 Тип работы: {order_data['work_type']}\n"
        f"📅 Дедлайн: {order_data['deadline']}\n"
    )

    if order_data.get('budget', 0) > 0:
        message += f"💰 Бюджет: {order_data['budget']} руб.\n"
    else:
        message += "💰 Бюджет: Цену назначит эксперт\n"

    if order_data.get('plagiarism_required', False):
        message += (
            f"🔍 Антиплагиат: {order_data.get('plagiarism_system_name', 'Неизвестная система')}\n"
            f"📊 Требуемый процент: {order_data.get('plagiarism_percent', 0)}%\n"
        )

    message += f"📎 Файлов: {len(order_data.get('files', []))}\n"

    if order_data.get('description'):
        message += f"📄 Описание: {order_data.get('description')[:100]}...\n"

    message += "\n⏳ Ожидайте, с вами свяжется эксперт для уточнения деталей."

    # Отправляем сообщение пользователю в зависимости от типа update
    if update.message:
        await update.message.reply_text(message, reply_markup=get_user_main_keyboard())
    elif update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=get_user_main_keyboard())

    # Уведомляем администратора о новом заказе
    try:
        admin_message = (
            f"🆕 Новый заказ #{order_id}\n\n"
            f"👤 Пользователь: @{order_data['username']} (ID: {order_data['user_id']})\n"
            f"📚 Дисциплина: {order_data['discipline']}\n"
            f"📝 Тип работы: {order_data['work_type']}\n"
            f"📅 Дедлайн: {order_data['deadline']}\n"
        )

        if order_data.get('budget', 0) > 0:
            admin_message += f"💰 Бюджет: {order_data['budget']} руб.\n"
        else:
            admin_message += "💰 Бюджет: Цену назначит эксперт\n"

        if order_data.get('plagiarism_required', False):
            admin_message += f"🔍 Антиплагиат: {order_data.get('plagiarism_system_name', 'Неизвестная система')}\n"
            admin_message += f"📊 Требуемый процент: {order_data.get('plagiarism_percent', 0)}%\n"

        if order_data.get('description'):
            admin_message += f"📄 Описание: {order_data.get('description')}\n"

        admin_message += f"📎 Файлов: {len(order_data.get('files', []))}\n"

        # Отправляем сообщение администратору
        await context.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=admin_message
        )

        # Если есть файлы, отправляем их администратору
        if order_data.get('files'):
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text=f"📎 Заказ #{order_id} содержит {len(order_data['files'])} файлов."
            )

    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")

    return USER_SELECTING_ACTION


async def user_my_orders(update: Update, context: CallbackContext):
    """Просмотр заказов пользователя"""
    query = update.callback_query
    await query.answer()

    user_id = context.user_data.get('user_id')

    # Получаем заказы пользователя
    orders = database.get_user_orders(user_id)

    if not orders:
        await query.edit_message_text(
            "У вас пока нет заказов.",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    # Сохраняем заказы в контексте для пагинации
    context.user_data['user_orders'] = orders
    context.user_data['orders_page'] = 0

    # Показываем первую страницу заказов
    return await show_orders_page(update, context, 0)


async def show_orders_page(update: Update, context: CallbackContext, page=0):
    """Показать страницу с заказами"""
    orders = context.user_data.get('user_orders', [])
    orders_per_page = 5
    total_pages = (len(orders) + orders_per_page - 1) // orders_per_page

    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0

    context.user_data['orders_page'] = page

    # Получаем заказы для текущей страницы
    start_idx = page * orders_per_page
    end_idx = min((page + 1) * orders_per_page, len(orders))
    current_orders = orders[start_idx:end_idx]

    message = "📋 Ваши заказы:\n\n"

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
        }.get(order['status'], '❓')

        message += f"{i}. {status_emoji} Заказ #{order['order_id']}\n"
        message += f"   📚 {order['discipline']} - {order['work_type']}\n"
        message += f"   🔄 {Config.ORDER_STATUSES.get(order['status'], order['status'])}\n"
        message += f"   📅 {order['deadline']}\n\n"

    message += f"Страница {page + 1}/{total_pages}"

    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=get_orders_list_keyboard(current_orders, page, total_pages)
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=get_orders_list_keyboard(current_orders, page, total_pages)
        )

    return USER_VIEWING_ORDERS


async def user_view_order(update: Update, context: CallbackContext):
    """Просмотр деталей конкретного заказа"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('user_view_order_', '')

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if not order:
        await query.edit_message_text("Заказ не найден.")
        return USER_VIEWING_ORDERS

    # Формируем сообщение с деталями заказа
    message = (
        f"📋 Заказ #{order['order_id']}\n"
        f"👤 Ваш ID: {order['user_id']}\n"
        f"📚 Дисциплина: {order['discipline']}\n"
        f"📝 Тип работы: {order['work_type']}\n"
        f"📅 Дедлайн: {order['deadline']}\n"
        f"💰 Бюджет: {order['budget']} руб.\n"
        f"💵 Итоговая цена: {order['final_amount']} руб.\n"
        f"🔄 Статус: {Config.ORDER_STATUSES.get(order['status'], order['status'])}\n"
    )

    # Добавляем информацию о антиплагиате, если требуется
    if order['plagiarism_required']:
        plagiarism_system = Config.PLAGIARISM_SYSTEMS.get(order['plagiarism_system'], {}).get('name', 'Не указана')
        message += f"🔍 Система антиплагиата: {plagiarism_system}\n"
        message += f"📊 Требуемый процент: {order['plagiarism_percent']}%\n"

    # Добавляем информацию о файлах
    if order['files']:
        message += f"📎 Исходные файлы: {order['files']}\n"

    if order['completed_files']:
        message += f"📦 Готовые файлы: {order['completed_files']}\n"

    # Проверяем, можно ли скачать файлы
    can_download = False
    if order['status'] == 'completed' and order['completed_at']:
        can_download = utils.is_file_available(order['completed_at'])
        if can_download:
            message += "\n✅ Файлы готовой работы доступны для скачивания"
        else:
            message += "\n❌ Файлы больше не доступны (прошло более 30 дней)"

    await query.edit_message_text(
        message,
        reply_markup=get_order_details_keyboard(order_id, order['status'], can_download)
    )

    return USER_ORDER_DETAILS


async def user_download_work(update: Update, context: CallbackContext):
    """Скачивание выполненной работы"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace('user_download_work_', '')

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)

    if not order or order['status'] != 'completed' or not order['completed_at']:
        await query.answer("Работа не доступна для скачивания.")
        return USER_ORDER_DETAILS

    # Проверяем срок доступности файлов
    if not utils.is_file_available(order['completed_at']):
        await query.answer("Срок скачивания истек (30 дней).")
        return USER_ORDER_DETAILS

    # Отправляем файлы пользователю
    user_id = order['user_id']
    completed_folder = utils.create_order_folder(order_id, user_id, "completed")

    if completed_folder and completed_folder.exists():
        files = list(completed_folder.glob('*'))
        for file in files:
            if file.is_file():
                try:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=open(file, 'rb'),
                        caption=f"Файл из заказа #{order_id}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки файла {file.name}: {e}")

        await query.answer("Файлы отправлены в чат.")
    else:
        await query.answer("Файлы не найдены.")

    return USER_ORDER_DETAILS


async def user_back_to_orders(update: Update, context: CallbackContext):
    """Возврат к списку заказов"""
    query = update.callback_query
    await query.answer()

    page = context.user_data.get('orders_page', 0)
    return await show_orders_page(update, context, page)


async def user_orders_navigation(update: Update, context: CallbackContext):
    """Навигация по страницам заказов"""
    query = update.callback_query
    await query.answer()

    data = query.data
    current_page = context.user_data.get('orders_page', 0)

    if data.startswith('user_orders_prev_'):
        new_page = int(data.replace('user_orders_prev_', ''))
    elif data.startswith('user_orders_next_'):
        new_page = int(data.replace('user_orders_next_', ''))
    else:
        new_page = current_page

    return await show_orders_page(update, context, new_page)


async def user_info(update: Update, context: CallbackContext):
    """Открытие информационного раздела"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "ℹ️ Информация\n\n"
        "Здесь вы можете узнать о возможностях бота, стоимости услуг и правилах работы.",
        reply_markup=get_info_keyboard()
    )

    return USER_INFO_MENU


async def user_info_commands(update: Update, context: CallbackContext):
    """Информация о командах"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📋 Список команд:\n\n"
        "/start - Начать работы с ботом\n"
        "/cancel - Отменить текущее действие\n\n"
        "Основные действия доступны через кнопки меню.\n\n"
        "👉 Подпишитесь на наш канал: @AssistSTUD",
        reply_markup=get_back_to_info_keyboard()
    )

    return USER_INFO_MENU


async def user_info_prices(update: Update, context: CallbackContext):
    """Информация о ценах"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💰 Стоимость услуг:\n\n"
        "📊 Примерные цены и сроки:\n\n"
        "📝 Доклад - от 3 часов, от 500₽\n"
        "✅ Тест - от 2 часов, от 300₽\n"
        "🧪 Лабораторная работа - от 4 часов, от 500₽\n"
        "🎫 Ответы на билеты - от 2 часов, от 400₽\n"
        "🎓 Дипломная работа - от 3 дней, от 5000₽\n"
        "📋 Отчет по практике - от 1 дня, от 1000₽\n\n"
        "📌 Окончательная цена зависит от:\n"
        "• Сложности дисциплины\n"
        "• Объема работы\n"
        "• Срочности выполнения\n"
        "• Требований к антиплагиату\n\n"
        "Точную стоимость вам назовет эксперт после изучения задания.\n\n"
        "👉 Подпишитесь на наш канал: @AssistSTUD",
        reply_markup=get_back_to_info_keyboard()
    )

    return USER_INFO_MENU


async def user_info_requisites(update: Update, context: CallbackContext):
    """Информация о реквизитах"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📄 Реквизиты для оплаты:\n\n"
        "Оплата принимается через:\n"
        "• Robokassa (банковские карты, электронные кошельки)\n"
        "• ЮMoney\n"
        "• QIWI\n\n"
        "После подтверждения заказа вам будет отправлена платежная ссылка.",
        reply_markup=get_back_to_info_keyboard()
    )

    return USER_INFO_MENU


async def user_info_rules(update: Update, context: CallbackContext):
    """Информация о правилах"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📝 Правила работы:\n\n"
        "1. Оплата производится после согласования цены с экспертом\n"
        "2. Возврат средств возможен при отмене заказа до начала работы\n"
        "3. Гарантируем конфиденциальность ваших данных\n"
        "4. Работы выполняются в соответствии с вашими требованиями\n"
        "5. Возможны доработки в случае несоответствия требованиям\n\n"
        "👉 Подпишитесь на наш канал: @AssistSTUD",
        reply_markup=get_back_to_info_keyboard()
    )

    return USER_INFO_MENU


async def user_info_back(update: Update, context: CallbackContext):
    """Возврат к информационному меню"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "ℹ️ Информация\n\n"
        "Здесь вы можете узнать о возможностях бота, стоимость услуг и правилах работы.",
        reply_markup=get_info_keyboard()
    )

    return USER_INFO_MENU


# Обработчики для студента
async def student_approve_order(update: Update, context: CallbackContext):
    """Обработка подтверждения заказа студентом"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.split('_')[-1]

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)
    if not order:
        await query.edit_message_text("Заказ не найден.")
        return

    # Обновляем статус заказа
    database.update_order_status(order_id, 'waiting_payment')

    # Генерируем платежную ссылку
    from payment import generate_robokassa_payment_link
    payment_url = generate_robokassa_payment_link(
        order_id=order_id,
        amount=order['final_amount'],
        description=f"Оплата заказа #{order_id}",
        user_id=order['user_id']
    )

    # Обновляем платежную ссылку в базе
    database.update_payment_url(order_id, payment_url)

    # Отправляем сообщение с кнопкой оплаты
    payment_message = (
        f"✅ Заказ подтвержден!\n\n"
        f"Сумма к оплате: {order['final_amount']} руб.\n"
        f"Для оплаты перейдите по ссылке ниже.\n\n"
        f"После оплаты нажмите кнопку 'Я оплатил(а)'."
    )

    keyboard = get_payment_keyboard(order_id, order['final_amount'], order['user_id'])

    await query.edit_message_text(payment_message, reply_markup=keyboard)

    # Уведомляем администратора
    try:
        from main import application
        await application.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"Студент подтвердил заказ #{order_id}. Ожидается оплата."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")


async def student_reject_order(update: Update, context: CallbackContext):
    """Обработка отмены заказа студентом"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.split('_')[-1]

    # Получаем информацию о заказе
    order = database.get_order_details(order_id)
    if not order:
        await query.edit_message_text("Заказ не найден.")
        return

    # Удаляем заказ из базы данных
    database.delete_order(order_id)

    # Удаляем файлы заказа
    if order:
        user_id = order['user_id']
        order_folder = utils.create_order_folder(order_id, user_id)
        if order_folder and order_folder.exists():
            shutil.rmtree(order_folder)

    # Уведомляем администратора
    try:
        from main import application
        await application.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"Студент отклонил заказ #{order_id}. Заказ удален."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")

    await query.edit_message_text("❌ Заказ отменен и удален.")


async def student_paid_order(update: Update, context: CallbackContext):
    """Обработка подтверждения оплаты студентом"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.split('_')[-1]

    # Обновляем статус заказа
    database.update_order_status(order_id, 'paid')
    database.update_payment_status(order_id, 'paid')

    # Уведомляем администратора
    try:
        from main import application
        await application.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"Студент оплатил заказ #{order_id}. Можно приступать к выполнению."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")

    await query.edit_message_text("✅ Оплата подтверждена. Эксперт приступит к работе в ближайшее время.")


async def student_accept_work(update: Update, context: CallbackContext):
    """Обработка принятия работы студентом"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.split('_')[-1]

    # Обновляем статус заказа
    database.update_order_status(order_id, 'completed')

    # Уведомляем администратора
    try:
        from main import application
        await application.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"Студент принял работу по заказу #{order_id}. Заказ завершен."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")

    await query.edit_message_text("✅ Работа принята. Спасибо за сотрудничество!")


async def student_request_revision(update: Update, context: CallbackContext):
    """Обработка запроса доработки студентом"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.split('_')[-1]

    # Обновляем статус заказа
    database.update_order_status(order_id, 'revision_requested')

    # Уведомляем администратора
    try:
        from main import application
        await application.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"Студент запросил доработку по заказу #{order_id}."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")

    await query.edit_message_text("✅ Запрос на доработку отправлен. Эксперт свяжется с вами в ближайшее время.")