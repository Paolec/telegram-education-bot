import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from datetime import datetime

from config import Config
from database import (
    save_order_to_db, get_user_orders, update_payment_url,
    update_order_status, get_order_details
)
from utils import (
    generate_order_id, create_order_folder, save_file,
    validate_deadline, validate_budget, validate_plagiarism_percent,
    split_long_message, log_errors
)
from keyboards import (
    get_disciplines_keyboard, get_work_types_keyboard,
    get_plagiarism_systems_keyboard, get_budget_type_keyboard,
    get_plagiarism_required_keyboard, get_upload_done_keyboard,
    get_skip_description_keyboard, get_user_main_keyboard,
    get_info_keyboard, get_back_to_info_keyboard,
    get_payment_confirmation_keyboard
)
from payment import generate_robokassa_payment_link

logger = logging.getLogger(__name__)

# Состояния разговора
USER_SELECTING_ACTION, USER_CHOOSE_DISCIPLINE, USER_CHOOSE_WORK_TYPE = range(3)
USER_SET_CUSTOM_WORK_TYPE, USER_SET_DEADLINE, USER_SELECT_BUDGET_TYPE = range(3, 6)
USER_SET_BUDGET, USER_SET_PLAGIARISM_REQUIRED, USER_CHOOSING_PLAGIARISM_SYSTEM = range(6, 9)
USER_SET_PLAGIARISM_PERCENT, USER_UPLOAD_FILES, USER_SET_DESCRIPTION = range(9, 12)
USER_VIEWING_ORDERS, USER_INFO_MENU = range(12, 14)


@log_errors
async def user_start(update: Update, context: CallbackContext):
    """Обработка команды /start для пользователя"""
    user = update.effective_user
    context.user_data.clear()

    welcome_text = (
        f"👋 Добро пожаловать, {user.first_name}!\n\n"
        "Я помогу вам заказать учебную работу. Выберите действие:"
    )

    if update.message:
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_user_main_keyboard()
        )
    else:
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=get_user_main_keyboard()
        )

    return USER_SELECTING_ACTION


@log_errors
async def user_cancel(update: Update, context: CallbackContext):
    """Обработка команды отмены"""
    user = update.effective_user
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Действие отменено. Используйте /start для начала работы.",
        reply_markup=get_user_main_keyboard()
    )

    return USER_SELECTING_ACTION


@log_errors
async def user_create_order(update: Update, context: CallbackContext):
    """Начало создания заказа"""
    query = update.callback_query
    await query.answer()

    # Проверяем количество активных заказов
    from database import get_user_active_orders_count
    active_orders = get_user_active_orders_count(query.from_user.id)

    if active_orders >= Config.MAX_ACTIVE_ORDERS:
        await query.edit_message_text(
            f"❌ У вас уже {active_orders} активных заказов. "
            f"Максимальное количество одновременно активных заказов: {Config.MAX_ACTIVE_ORDERS}.",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    context.user_data['order'] = {
        'user_id': query.from_user.id,
        'username': query.from_user.username or query.from_user.full_name
    }

    disciplines_text = (
        "📚 Выберите дисциплину для вашей работы:\n\n"
        "Если нужной дисциплины нет в списке, выберите наиболее подходящую, "
        "а уточнения можно будет указать в описании."
    )

    await query.edit_message_text(
        disciplines_text,
        reply_markup=get_disciplines_keyboard()
    )

    return USER_CHOOSE_DISCIPLINE


@log_errors
async def user_choose_discipline(update: Update, context: CallbackContext):
    """Обработка выбора дисциплины"""
    query = update.callback_query
    await query.answer()

    if query.data == "user_back_to_start":
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    # Извлекаем ID дисциплины из callback_data
    disc_id = query.data.replace("user_disc_", "")

    # Находим название дисциплины по ID
    disc_name = next((name for id, name in Config.DISCIPLINES if id == disc_id), "Неизвестная дисциплина")

    # Сохраняем в контексте
    context.user_data['order']['discipline'] = disc_name
    context.user_data['order']['discipline_id'] = disc_id

    work_types_text = (
        f"📋 Выберите тип работы для дисциплины '{disc_name}':\n\n"
        "Если нужного типа работы нет в списке, выберите 'Другое' "
        "и укажите подробности в описании."
    )

    await query.edit_message_text(
        work_types_text,
        reply_markup=get_work_types_keyboard()
    )

    return USER_CHOOSE_WORK_TYPE


@log_errors
async def user_choose_work_type(update: Update, context: CallbackContext):
    """Обработка выбора типа работы"""
    query = update.callback_query
    await query.answer()

    if query.data == "user_back_to_disciplines":
        disciplines_text = "📚 Выберите дисциплину для вашей работы:"
        await query.edit_message_text(
            disciplines_text,
            reply_markup=get_disciplines_keyboard()
        )
        return USER_CHOOSE_DISCIPLINE

    # Извлекаем ID типа работы из callback_data
    work_id = query.data.replace("user_work_", "")

    # Находим название типа работы по ID
    work_name = next((name for id, name in Config.WORK_TYPES if id == work_id), "Неизвестный тип работы")

    # Сохраняем в контексте
    context.user_data['order']['work_type'] = work_name
    context.user_data['order']['work_type_id'] = work_id

    if work_id == "other":
        await query.edit_message_text(
            "✏️ Укажите тип работы своими словами:",
            reply_markup=get_back_to_info_keyboard()
        )
        return USER_SET_CUSTOM_WORK_TYPE

    await query.edit_message_text(
        "📅 Укажите дедлайн для выполнения работы в формате ДД.ММ.ГГГГ (например, 25.08.2025):"
    )

    return USER_SET_DEADLINE


@log_errors
async def user_set_custom_work_type(update: Update, context: CallbackContext):
    """Обработка ввода пользовательского типа работы"""
    custom_work_type = update.message.text

    if len(custom_work_type) > 100:
        await update.message.reply_text(
            "❌ Слишком длинное название. Укажите тип работы короче (макс. 100 символов):"
        )
        return USER_SET_CUSTOM_WORK_TYPE

    context.user_data['order']['work_type'] = custom_work_type
    context.user_data['order']['work_type_id'] = "custom"

    await update.message.reply_text(
        "📅 Укажите дедлайн для выполнения работы в формате ДД.ММ.ГГГГ (например, 25.08.2025):"
    )

    return USER_SET_DEADLINE


@log_errors
async def user_handle_deadline(update: Update, context: CallbackContext):
    """Обработка ввода дедлайна"""
    deadline_str = update.message.text
    is_valid, result = validate_deadline(deadline_str)

    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nПопробуйте еще раз:")
        return USER_SET_DEADLINE

    context.user_data['order']['deadline'] = deadline_str

    budget_text = (
        "💰 Выберите способ определения бюджета:\n\n"
        "• Указать свой бюджет - вы сами устанавливаете сумму, которую готовы заплатить\n"
        "• Цену назначит эксперт - мы оценим работу и предложим оптимальную цену"
    )

    await update.message.reply_text(
        budget_text,
        reply_markup=get_budget_type_keyboard()
    )

    return USER_SELECT_BUDGET_TYPE


@log_errors
async def user_handle_budget_type(update: Update, context: CallbackContext):
    """Обработка выбора типа бюджета"""
    query = update.callback_query
    await query.answer()

    if query.data == "user_set_budget":
        await query.edit_message_text(
            f"💰 Укажите ваш бюджет в рублях (минимальная сумма - {Config.MIN_BUDGET} руб.):"
        )
        return USER_SET_BUDGET
    else:  # user_expert_budget
        context.user_data['order']['budget'] = 0  # 0 означает, что цену установит эксперт

        plagiarism_text = (
            "🔍 Требуется ли проверка на антиплагиат?\n\n"
            "Мы можем проверить работу через системы антиплагиата и предоставить отчет."
        )

        await query.edit_message_text(
            plagiarism_text,
            reply_markup=get_plagiarism_required_keyboard()
        )
        return USER_SET_PLAGIARISM_REQUIRED


@log_errors
async def user_handle_budget(update: Update, context: CallbackContext):
    """Обработка ввода бюджета"""
    budget_str = update.message.text
    is_valid, result = validate_budget(budget_str)

    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nПопробуйте еще раз:")
        return USER_SET_BUDGET

    context.user_data['order']['budget'] = result

    plagiarism_text = (
        "🔍 Требуется ли проверка на антиплагиат?\n\n"
        "Мы можем проверить работу через системы антиплагиата и предоставить отчет."
    )

    await update.message.reply_text(
        plagiarism_text,
        reply_markup=get_plagiarism_required_keyboard()
    )

    return USER_SET_PLAGIARISM_REQUIRED


@log_errors
async def user_handle_plagiarism_required(update: Update, context: CallbackContext):
    """Обработка необходимости проверки на антиплагиат"""
    query = update.callback_query
    await query.answer()

    if query.data == "user_plagiarism_yes":
        context.user_data['order']['plagiarism_required'] = 1

        systems_text = "🔍 Выберите систему проверки антиплагиата:"

        await query.edit_message_text(
            systems_text,
            reply_markup=get_plagiarism_systems_keyboard()
        )
        return USER_CHOOSING_PLAGIARISM_SYSTEM
    else:
        context.user_data['order']['plagiarism_required'] = 0
        context.user_data['order']['plagiarism_system'] = ""
        context.user_data['order']['plagiarism_percent'] = 0

        files_text = (
            "📎 Теперь загрузите файлы с заданием (если есть).\n\n"
            "Вы можете прикреплять документы, изображения или архивные файлы. "
            "После загрузки всех файлов нажмите 'Завершить загрузку'."
        )

        await query.edit_message_text(
            files_text,
            reply_markup=get_upload_done_keyboard()
        )
        return USER_UPLOAD_FILES


@log_errors
async def user_handle_plagiarism_system(update: Update, context: CallbackContext):
    """Обработка выбора системы антиплагиата"""
    query = update.callback_query
    await query.answer()

    system_id = query.data.replace("user_plag_sys_", "")
    system_data = Config.PLAGIARISM_SYSTEMS.get(system_id, {})

    context.user_data['order']['plagiarism_system'] = system_data.get('name', 'Неизвестная система')
    context.user_data['order']['plagiarism_system_id'] = system_id

    await query.edit_message_text(
        "🔢 Укажите требуемый процент оригинальности (от 0 до 100):"
    )

    return USER_SET_PLAGIARISM_PERCENT


@log_errors
async def user_handle_plagiarism_percent(update: Update, context: CallbackContext):
    """Обработка ввода процента антиплагиата"""
    percent_str = update.message.text
    is_valid, result = validate_plagiarism_percent(percent_str)

    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nПопробуйте еще раз:")
        return USER_SET_PLAGIARISM_PERCENT

    context.user_data['order']['plagiarism_percent'] = result

    files_text = (
        "📎 Теперь загрузите файлы с заданием (если есть).\n\n"
        "Вы можете прикреплять документы, изображения или архивные файлы. "
        "После загрузки всех файлов нажмите 'Завершить загрузку'."
    )

    await update.message.reply_text(
        files_text,
        reply_markup=get_upload_done_keyboard()
    )

    return USER_UPLOAD_FILES


@log_errors
async def user_handle_files(update: Update, context: CallbackContext):
    """Обработка загрузки файлов"""
    if 'order' not in context.user_data:
        await update.message.reply_text(
            "❌ Произошла ошибка. Начните заново с команды /start."
        )
        return USER_SELECTING_ACTION

    # Создаем папку для заказа, если еще не создана
    if 'order_id' not in context.user_data['order']:
        order_id = generate_order_id(update.effective_user.id)
        context.user_data['order']['order_id'] = order_id
        order_folder = create_order_folder(order_id, update.effective_user.id)
        context.user_data['order_folder'] = order_folder
    else:
        order_folder = context.user_data.get('order_folder')

    # Сохраняем файл
    if update.message.document:
        file = update.message.document
    elif update.message.photo:
        file = update.message.photo[-1]  # Берем самое качественное фото
    else:
        await update.message.reply_text(
            "❌ Формат файла не поддерживается. Используйте документы или изображения."
        )
        return USER_UPLOAD_FILES

    # Проверяем размер файла
    if file.file_size > Config.MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ Файл слишком большой. Максимальный размер: {Config.MAX_FILE_SIZE // 1024 // 1024}MB."
        )
        return USER_UPLOAD_FILES

    # Проверяем тип файла
    if hasattr(file, 'mime_type') and file.mime_type not in Config.ALLOWED_FILE_TYPES:
        await update.message.reply_text(
            "❌ Тип файла не поддерживается. Используйте PDF, Word, Excel, изображения или архивы."
        )
        return USER_UPLOAD_FILES

    # Сохраняем файл
    file_path = await save_file(file, order_folder)

    if file_path:
        if 'files' not in context.user_data:
            context.user_data['files'] = []
        context.user_data['files'].append(file_path)

        await update.message.reply_text(
            f"✅ Файл сохранен. Загружено файлов: {len(context.user_data['files'])}\n\n"
            "Продолжайте загрузку или нажмите 'Завершить загрузку'.",
            reply_markup=get_upload_done_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при сохранении файла. Попробуйте еще раз."
        )

    return USER_UPLOAD_FILES


@log_errors
async def user_handle_upload_done(update: Update, context: CallbackContext):
    """Обработка завершения загрузки файлов"""
    query = update.callback_query
    await query.answer()

    if 'files' in context.user_data:
        context.user_data['order']['files'] = context.user_data['files']

    description_text = (
        "📝 Добавьте описание к заказу (необязательно):\n\n"
        "Укажите дополнительные детали, требования, методички или другую важную информацию. "
        "Если описание не нужно, нажмите 'Пропустить описание'."
    )

    await query.edit_message_text(
        description_text,
        reply_markup=get_skip_description_keyboard()
    )

    return USER_SET_DESCRIPTION


@log_errors
async def user_handle_description(update: Update, context: CallbackContext):
    """Обработка ввода описания"""
    description = update.message.text

    if len(description) > 2000:
        await update.message.reply_text(
            "❌ Описание слишком длинное. Максимальная длина - 2000 символов.\n\nПопробуйте еще раз:",
            reply_markup=get_skip_description_keyboard()
        )
        return USER_SET_DESCRIPTION

    context.user_data['order']['description'] = description

    # Сохраняем заказ в БД
    order_id = save_order_to_db(context.user_data['order'])

    if not order_id:
        await update.message.reply_text(
            "❌ Произошла ошибка при создании заказа. Попробуйте еще раз.",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    # Формируем информацию о заказе
    order = context.user_data['order']
    order_info = (
        f"✅ Заказ #{order_id} создан!\n\n"
        f"📚 Дисциплина: {order.get('discipline', 'Не указано')}\n"
        f"📋 Тип работы: {order.get('work_type', 'Не указано')}\n"
        f"📅 Дедлайн: {order.get('deadline', 'Не указано')}\n"
    )

    if order.get('budget', 0) > 0:
        order_info += f"💰 Бюджет: {order['budget']} руб.\n"
    else:
        order_info += "💰 Бюджет: Цену назначит эксперт\n"

    if order.get('plagiarism_required', 0) == 1:
        order_info += (
            f"🔍 Антиплагиат: {order.get('plagiarism_system', 'Не указано')}\n"
            f"📊 Требуемый процент: {order.get('plagiarism_percent', 0)}%\n"
        )

    if order.get('description'):
        order_info += f"📝 Описание: {order['description'][:100]}...\n"

    order_info += f"\n📎 Файлов: {len(order.get('files', []))}"

    order_info += (
        f"\n\n📞 Администратор свяжется с вами в ближайшее время для уточнения деталей. "
        f"Вы можете отслеживать статус заказа в разделе 'Мои заказы'."
    )

    await update.message.reply_text(order_info)

    # Уведомляем администратора
    admin_message = (
        f"🆕 Новый заказ #{order_id}\n"
        f"👤 Пользователь: {order['username']} (ID: {order['user_id']})\n"
        f"📚 Дисциплина: {order.get('discipline', 'Не указано')}\n"
        f"📋 Тип работы: {order.get('work_type', 'Не указано')}\n"
        f"📅 Дедлайн: {order.get('deadline', 'Не указано')}\n"
    )

    if order.get('budget', 0) > 0:
        admin_message += f"💰 Бюджет: {order['budget']} руб.\n"
    else:
        admin_message += "💰 Бюджет: Цену назначит эксперт\n"

    await context.bot.send_message(chat_id=Config.ADMIN_ID, text=admin_message)

    # Очищаем данные заказа
    context.user_data.clear()

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=get_user_main_keyboard()
    )

    return USER_SELECTING_ACTION


@log_errors
async def user_skip_description(update: Update, context: CallbackContext):
    """Пропуск описания"""
    query = update.callback_query
    await query.answer()

    context.user_data['order']['description'] = ""

    # Сохраняем заказ в БД
    order_id = save_order_to_db(context.user_data['order'])

    if not order_id:
        await query.edit_message_text(
            "❌ Произошла ошибка при создании заказа. Попробуйте еще раз.",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    # Формируем информацию о заказе
    order = context.user_data['order']
    order_info = (
        f"✅ Заказ #{order_id} создан!\n\n"
        f"📚 Дисциплина: {order.get('discipline', 'Не указано')}\n"
        f"📋 Тип работы: {order.get('work_type', 'Не указано')}\n"
        f"📅 Дедлайн: {order.get('deadline', 'Не указано')}\n"
    )

    if order.get('budget', 0) > 0:
        order_info += f"💰 Бюджет: {order['budget']} руб.\n"
    else:
        order_info += "💰 Бюджет: Цену назначит эксперт\n"

    if order.get('plagiarism_required', 0) == 1:
        order_info += (
            f"🔍 Антиплагиат: {order.get('plagiarism_system', 'Не указано')}\n"
            f"📊 Требуемый процент: {order.get('plagiarism_percent', 0)}%\n"
        )

    order_info += f"📎 Файлов: {len(order.get('files', []))}"

    order_info += (
        f"\n\n📞 Администратор свяжется с вами в ближайшее время для уточнения деталей. "
        f"Вы можете отслеживать статус заказа в разделе 'Мои заказы'."
    )

    await query.edit_message_text(order_info)

    # Уведомляем администратора
    admin_message = (
        f"🆕 Новый заказ #{order_id}\n"
        f"👤 Пользователь: {order['username']} (ID: {order['user_id']})\n"
        f"📚 Дисциплина: {order.get('discipline', 'Не указано')}\n"
        f"📋 Тип работы: {order.get('work_type', 'Не указано')}\n"
        f"📅 Дедлайн: {order.get('deadline', 'Не указано')}\n"
    )

    if order.get('budget', 0) > 0:
        admin_message += f"💰 Бюджет: {order['budget']} руб.\n"
    else:
        admin_message += "💰 Бюджет: Цену назначит эксперт\n"

    await context.bot.send_message(chat_id=Config.ADMIN_ID, text=admin_message)

    # Очищаем данные заказа
    context.user_data.clear()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Выберите действие:",
        reply_markup=get_user_main_keyboard()
    )

    return USER_SELECTING_ACTION


@log_errors
async def user_my_orders(update: Update, context: CallbackContext):
    """Просмотр заказов пользователя"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    orders = get_user_orders(user_id)

    if not orders:
        await query.edit_message_text(
            "📋 У вас пока нет заказов.\n\nСоздайте первый заказ, нажав на кнопку ниже:",
            reply_markup=get_user_main_keyboard()
        )
        return USER_SELECTING_ACTION

    # Формируем список заказов
    orders_text = "📋 Ваши заказы:\n\n"

    for i, order in enumerate(orders, 1):
        status_emoji = {
            'new': '🔍',
            'in_progress': '🛠',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order['status'], '❓')

        orders_text += (
            f"{i}. #{order['order_id']} - {status_emoji} {Config.ORDER_STATUSES.get(order['status'], order['status'])}\n"
            f"   📚 {order.get('discipline', 'Не указано')} - {order.get('work_type', 'Не указано')}\n"
            f"   📅 {order.get('deadline', 'Не указано')}\n"
        )

        if order.get('final_amount', 0) > 0:
            orders_text += f"   💰 {order['final_amount']} руб.\n"

        orders_text += "\n"

    orders_text += "Выберите действие:"

    await query.edit_message_text(
        orders_text,
        reply_markup=get_user_main_keyboard()
    )

    return USER_SELECTING_ACTION


@log_errors
async def student_approve_order(update: Update, context: CallbackContext):
    """Обработка подтверждения заказа студентом"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace("student_approve_", "")
    order_details = get_order_details(order_id)

    if not order_details:
        await query.edit_message_text("❌ Заказ не найден.")
        return ConversationHandler.END

    # Обновляем статус заказа
    update_order_status(order_id, "completed")

    # Уведомляем администратора
    await context.bot.send_message(
        chat_id=Config.ADMIN_ID,
        text=f"✅ Студент подтвердил выполнение заказа #{order_id}"
    )

    await query.edit_message_text(
        f"✅ Вы подтвердили выполнение заказа #{order_id}. Спасибо за сотрудничество!"
    )

    return ConversationHandler.END


@log_errors
async def student_reject_order(update: Update, context: CallbackContext):
    """Обработка отклонения заказа студентом"""
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace("student_reject_", "")
    order_details = get_order_details(order_id)

    if not order_details:
        await query.edit_message_text("❌ Заказ не найден.")
        return ConversationHandler.END

    # Уведомляем администратора
    await context.bot.send_message(
        chat_id=Config.ADMIN_ID,
        text=f"❌ Студент отклонил выполнение заказа #{order_id}. Требуется доработка."
    )

    await query.edit_message_text(
        f"❌ Вы отклонили выполнение заказа #{order_id}. Администратор свяжется с вами для уточнения деталей."
    )

    return ConversationHandler.END


# Новые обработчики для информационного раздела
@log_errors
async def user_info(update: Update, context: CallbackContext):
    """Обработка кнопки информации"""
    query = update.callback_query
    await query.answer()

    message_text = (
        "ℹ️ *Информационный раздел*\n\n"
        "Здесь вы можете узнать о возможностях бота, стоимости услуг, "
        "реквизитах и правилах работы."
    )

    await query.edit_message_text(
        text=message_text,
        reply_markup=get_info_keyboard(),
        parse_mode='Markdown'
    )
    return USER_INFO_MENU


@log_errors
async def user_info_commands(update: Update, context: CallbackContext):
    """Информация о командах бота"""
    query = update.callback_query
    await query.answer()

    commands_text = (
        "📋 *Список команд бота:*\n\n"
        "*/start* - Запустить бота\n"
        "*/cancel* - Отменить текущее действие\n"
        "*/admin* - Панель администратора\n\n"
        "*Основные возможности:*\n"
        "• Создание заказов на учебные работы\n"
        "• Отслеживание статуса заказов\n"
        "• Общение с исполнителем\n"
        "• Оплата через безопасную систему\n"
    )

    await query.edit_message_text(
        text=commands_text,
        reply_markup=get_back_to_info_keyboard(),
        parse_mode='Markdown'
    )
    return USER_INFO_MENU


@log_errors
async def user_info_prices(update: Update, context: CallbackContext):
    """Информация о стоимости услуг"""
    query = update.callback_query
    await query.answer()

    prices_text = (
        "💰 *Стоимость услуг помощи в написании работ:*\n\n"
        "• Решение задач: от 100р за задачу\n"
        "• Контрольная работа: от 300р\n"
        "• Курсовая работа: от 1000р\n"
        "• Дипломная работа: от 5000р\n"
        "• Лабораторная работа: от 400р\n"
        "• Реферат: от 300р\n"
        "• Эссе: от 250р\n"
        "• Перевод: от 150р за страницу\n\n"
        "*Примечание:*\n"
        "Окончательная стоимость рассчитывается индивидуально "
        "в зависимости от сложности, сроков и требований к работе."
    )

    await query.edit_message_text(
        text=prices_text,
        reply_markup=get_back_to_info_keyboard(),
        parse_mode='Markdown'
    )
    return USER_INFO_MENU


@log_errors
async def user_info_requisites(update: Update, context: CallbackContext):
    """Информация о реквизитах"""
    query = update.callback_query
    await query.answer()

    requisites_text = (
        "📄 *Реквизиты самозанятого:*\n\n"
        "• ФИО: Одинцов П.В.\n"
        "• ИНН: 711809123388\n\n"
        "*Политика обработки персональных данных:*\n"
        "1. Мы собираем только необходимые данные для выполнения заказа\n"
        "2. Ваши данные не передаются третьим лицам\n"
        "3. Мы используем ваши контактные данные только для связи по поводу заказа\n"
        "4. После завершения работы все личные данные могут быть удалены по вашему запросу\n"
        "5. Мы используем безопасные методы хранения и передачи данных"
    )

    await query.edit_message_text(
        text=requisites_text,
        reply_markup=get_back_to_info_keyboard(),
        parse_mode='Markdown'
    )
    return USER_INFO_MENU


@log_errors
async def user_info_rules(update: Update, context: CallbackContext):
    """Информация о правилах работы"""
    query = update.callback_query
    await query.answer()

    rules_text = (
        "📝 *Правила оформления и условия работы:*\n\n"
        "*Сроки исполнения:*\n"
        "• Зависит от сложности работы и загруженности исполнителей\n"
        "• Минимальный срок - 1 день для простых задач\n"
        "• Средний срок для курсовых - 5-7 дней\n"
        "• Для дипломных работ - от 10 дней\n\n"
        "*Условия оплаты:*\n"
        "• Предоплата 30% для начала работы\n"
        "• Окончательная оплата после выполнения и проверки\n"
        "• Возможна оплата частями для крупных заказов\n"
        "• Оплата через Robokassa или другие платежные системы\n\n"
        "*Возврат/отказ от заказа:*\n"
        "• Возврат предоплаты при отказе до начала работы\n"
        "• При отказе во время выполнения работы возвращается часть средств\n"
        "• После выполнения работы возврат возможен только при нарушении условий"
    )

    await query.edit_message_text(
        text=rules_text,
        reply_markup=get_back_to_info_keyboard(),
        parse_mode='Markdown'
    )
    return USER_INFO_MENU


@log_errors
async def user_info_back(update: Update, context: CallbackContext):
    """Возврат из подраздела информации в главное меню информации"""
    query = update.callback_query
    await query.answer()

    message_text = (
        "ℹ️ *Информационный раздел*\n\n"
        "Здесь вы можете узнать о возможностях бота, стоимости услуг, "
        "реквизитах и правилах работы."
    )

    await query.edit_message_text(
        text=message_text,
        reply_markup=get_info_keyboard(),
        parse_mode='Markdown'
    )
    return USER_INFO_MENU


@log_errors
async def handle_wrong_input(update: Update, context: CallbackContext):
    """Обработка неправильного ввода"""
    await update.message.reply_text("Пожалуйста, введите текстовое сообщение.")
    return context.user_data.get('current_state', USER_SELECTING_ACTION)