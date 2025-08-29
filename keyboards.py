from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config


def get_disciplines_keyboard(prefix="user"):
    """Клавиатура выбора дисциплины"""
    keyboard = []
    for disc_id, disc_name in Config.DISCIPLINES:
        keyboard.append([InlineKeyboardButton(disc_name, callback_data=f"{prefix}_disc_{disc_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"{prefix}_back_to_start")])
    return InlineKeyboardMarkup(keyboard)


def get_work_types_keyboard(prefix="user"):
    """Клавиатура выбора типа работы"""
    keyboard = []
    for work_id, work_name in Config.WORK_TYPES:
        keyboard.append([InlineKeyboardButton(work_name, callback_data=f"{prefix}_work_{work_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"{prefix}_back_to_disciplines")])
    return InlineKeyboardMarkup(keyboard)


def get_plagiarism_systems_keyboard(prefix="user"):
    """Клавиатура выбора системы антиплагиата"""
    keyboard = []
    for sys_id, sys_data in Config.PLAGIARISM_SYSTEMS.items():
        btn_text = f"{sys_data['name']} {sys_data['emoji']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"{prefix}_plag_sys_{sys_id}")])
    return InlineKeyboardMarkup(keyboard)


def get_budget_type_keyboard(prefix="user"):
    """Клавиатура выбора типа бюджета"""
    keyboard = [
        [InlineKeyboardButton("💰 Указать свой бюджет", callback_data=f"{prefix}_set_budget")],
        [InlineKeyboardButton("🧑‍💼 Цену назначит эксперт", callback_data=f"{prefix}_expert_budget")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_plagiarism_required_keyboard(prefix="user"):
    """Клавиатура необходимости антиплагиата"""
    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data=f"{prefix}_plagiarism_yes")],
        [InlineKeyboardButton("❌ Нет", callback_data=f"{prefix}_plagiarism_no")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_upload_done_keyboard(prefix="user"):
    """Клавиатура завершения загрузки файлов"""
    keyboard = [
        [InlineKeyboardButton("✅ Завершить загрузку", callback_data=f"{prefix}_upload_done")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_skip_description_keyboard(prefix="user"):
    """Клавиатура пропуска описания"""
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить описание", callback_data=f"{prefix}_skip_description")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_main_keyboard():
    """Основная клавиатура админ-панели"""
    keyboard = [
        [InlineKeyboardButton("📋 Посмотреть все заказы", callback_data="admin_view_orders")],
        [InlineKeyboardButton("📝 Создать тестовый заказ", callback_data="admin_test_order")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_order_actions_keyboard(order_id):
    """Клавиатура действий с заказом для админа"""
    keyboard = [
        [InlineKeyboardButton("💬 Отправить сообщение студенту", callback_data=f"admin_send_msg_{order_id}")],
        [InlineKeyboardButton("💰 Назначить цену", callback_data=f"admin_set_price_{order_id}")],
        [InlineKeyboardButton("📤 Загрузить выполненную работу", callback_data=f"admin_upload_work_{order_id}")],
        [InlineKeyboardButton("✅ Подтвердить выполнение", callback_data=f"admin_complete_{order_id}")],
        [InlineKeyboardButton("❌ Отменить заказ", callback_data=f"admin_cancel_{order_id}")],
        [InlineKeyboardButton("🔙 Назад к списку заказов", callback_data="admin_view_orders")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_user_main_keyboard():
    """Основная клавиатура пользователя"""
    keyboard = [
        [InlineKeyboardButton("📝 Создать заказ", callback_data="user_create_order")],
        [InlineKeyboardButton("📋 Мои заказы", callback_data="user_my_orders")],
        [InlineKeyboardButton("ℹ️ Информация", callback_data="user_info")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_main_keyboard(prefix="user"):
    """Клавиатура возврата в главное меню"""
    keyboard = [
        [InlineKeyboardButton("🔙 На главную", callback_data=f"{prefix}_back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_info_keyboard(prefix="user"):
    """Клавиатура информационного раздела"""
    keyboard = [
        [InlineKeyboardButton("📋 Список команд", callback_data=f"{prefix}_info_commands")],
        [InlineKeyboardButton("💰 Стоимость услуг", callback_data=f"{prefix}_info_prices")],
        [InlineKeyboardButton("📄 Реквизиты", callback_data=f"{prefix}_info_requisites")],
        [InlineKeyboardButton("📝 Правила", callback_data=f"{prefix}_info_rules")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"{prefix}_back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_info_keyboard(prefix="user"):
    """Клавиатура возврата в информационное меню"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад к информации", callback_data=f"{prefix}_info_back")]
    ])


def get_payment_confirmation_keyboard(order_id, amount, user_id):
    """Клавиатура подтверждения оплаты"""
    from payment import generate_robokassa_payment_link

    payment_url = generate_robokassa_payment_link(
        order_id=order_id,
        amount=amount,
        description=f"Оплата заказа #{order_id}",
        user_id=user_id
    )

    keyboard = [
        [InlineKeyboardButton("💳 Оплатить заказ", url=payment_url)],
        [InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"user_paid_{order_id}")],
        [InlineKeyboardButton("❌ Отменить заказ", callback_data=f"user_cancel_order_{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_orders_navigation_keyboard(status, page=0, total_pages=1):
    """Клавиатура навигации по заказам для админа"""
    keyboard = []

    # Кнопки статусов
    status_buttons = [
        InlineKeyboardButton("🔍 Новые", callback_data="admin_orders_new"),
        InlineKeyboardButton("🛠 В работе", callback_data="admin_orders_in_progress"),
        InlineKeyboardButton("✅ Завершенные", callback_data="admin_orders_completed"),
        InlineKeyboardButton("❌ Отмененные", callback_data="admin_orders_cancelled")
    ]

    # Добавляем кнопки статусов в два ряда
    keyboard.append(status_buttons[:2])
    keyboard.append(status_buttons[2:])

    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"admin_orders_prev_{status}_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="admin_orders_page"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"admin_orders_next_{status}_{page + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")])

    return InlineKeyboardMarkup(keyboard)