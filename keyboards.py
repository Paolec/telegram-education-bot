from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pathlib import Path
from config import Config
from payment import generate_robokassa_payment_link

# Категории для шаблонов ответов
TEMPLATE_CATEGORIES = {
    'general': '📋 Общие',
    'price': '💰 Ценообразование',
    'deadline': '⏰ Сроки',
    'completion': '✅ Завершение работ',
    'revision': '🔄 Доработки'
}


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
        [InlineKeyboardButton("📋 Все заказы", callback_data="admin_view_all_orders")],
        [InlineKeyboardButton("🔍 Новые заказы", callback_data="admin_orders_new")],
        [InlineKeyboardButton("🛠 В работе", callback_data="admin_orders_in_progress")],
        [InlineKeyboardButton("✅ Завершенные", callback_data="admin_orders_completed")],
        [InlineKeyboardButton("📝 Управление шаблонами", callback_data="admin_manage_templates")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_order_actions_keyboard(order_id):
    """Клавиатура действий с заказом для админа"""
    keyboard = [
        [InlineKeyboardButton("💬 Написать студенту", callback_data=f"admin_send_msg_{order_id}")],
        [InlineKeyboardButton("💰 Установить цену", callback_data=f"admin_force_set_price_{order_id}")],
        [InlineKeyboardButton("📤 Загрузить работу", callback_data=f"admin_upload_work_{order_id}")],
        [InlineKeyboardButton("✅ Завершить заказ", callback_data=f"admin_complete_{order_id}")],
        [InlineKeyboardButton("🗑️ Полностью удалить", callback_data=f"admin_delete_completely_{order_id}")],
        [InlineKeyboardButton("🔙 Назад к списку", callback_data="admin_view_all_orders")]
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
        [InlineKeyboardButton("📝 Правила", callback_data=f"{prefix}_info_rules")],
        [InlineKeyboardButton("📢 Наш канал", url="https://t.me/AssistSTUD")],
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

    # Кнопки навигации (только если больше одной страницы)
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"admin_orders_prev_{status}_{page - 1}"))

        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="admin_orders_page"))

        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Вперед ➡️", callback_data=f"admin_orders_next_{status}_{page + 1}"))

        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")])

    return InlineKeyboardMarkup(keyboard)


def get_student_confirmation_keyboard(order_id, amount, user_id):
    """Клавиатура подтверждения заказа студентом"""
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить и оплатить", callback_data=f"student_approve_{order_id}")],
        [InlineKeyboardButton("❌ Отказаться", callback_data=f"student_reject_{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_payment_keyboard(order_id, amount, user_id):
    """Клавиатура оплаты"""
    payment_url = generate_robokassa_payment_link(
        order_id=order_id,
        amount=amount,
        description=f"Оплата заказа #{order_id}",
        user_id=user_id
    )

    keyboard = [
        [InlineKeyboardButton("💳 Оплатить заказ", url=payment_url)],
        [InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"student_paid_{order_id}")],
        [InlineKeyboardButton("❌ Отменить заказ", callback_data=f"student_cancel_{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_work_approval_keyboard(order_id):
    """Клавиатура принятия работы студентом"""
    keyboard = [
        [InlineKeyboardButton("✅ Принять работу", callback_data=f"student_accept_work_{order_id}")],
        [InlineKeyboardButton("🔄 Отправить на доработку", callback_data=f"student_revise_work_{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_orders_list_keyboard(orders, page=0, total_pages=1):
    """Клавиатура списка заказов пользователя"""
    keyboard = []

    for order in orders:
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

        keyboard.append([
            InlineKeyboardButton(
                f"{status_emoji} Заказ #{order['order_id']} - {Config.ORDER_STATUSES.get(order['status'], order['status'])}",
                callback_data=f"user_view_order_{order['order_id']}"
            )
        ])

    # Кнопки навигации
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"user_orders_prev_{page - 1}"))

        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="user_orders_page"))

        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"user_orders_next_{page + 1}"))

        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 На главную", callback_data="user_back_to_start")])

    return InlineKeyboardMarkup(keyboard)


def get_order_details_keyboard(order_id, status, can_download=False):
    """Клавиатура деталей заказа"""
    keyboard = []

    if can_download:
        keyboard.append([InlineKeyboardButton("📥 Скачать работу", callback_data=f"user_download_work_{order_id}")])

    if status == 'work_uploaded':
        keyboard.append([InlineKeyboardButton("✅ Принять работу", callback_data=f"user_accept_work_{order_id}")])
        keyboard.append(
            [InlineKeyboardButton("🔄 Запросить доработку", callback_data=f"user_request_revision_{order_id}")])

    keyboard.append([InlineKeyboardButton("💬 Написать эксперту", callback_data=f"user_message_expert_{order_id}")])
    keyboard.append([InlineKeyboardButton("🔙 К списку заказов", callback_data="user_back_to_orders")])

    return InlineKeyboardMarkup(keyboard)


def get_admin_templates_keyboard(templates):
    """Клавиатура шаблонов ответов для админа"""
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

        for template in category_templates:
            keyboard.append([
                InlineKeyboardButton(
                    f"{category_name} - {template['name']}",
                    callback_data=f"admin_use_template_{template['id']}"
                )
            ])

    keyboard.append([InlineKeyboardButton("➕ Создать шаблон", callback_data="admin_create_template")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

    return InlineKeyboardMarkup(keyboard)


def get_template_categories_keyboard():
    """Клавиатура выбора категории для шаблона"""
    keyboard = []

    for category_id, category_name in TEMPLATE_CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(category_name, callback_data=f"admin_template_category_{category_id}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_manage_templates")])

    return InlineKeyboardMarkup(keyboard)


def get_back_to_templates_keyboard():
    """Клавиатура возврата к управлению шаблонами"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад к шаблонам", callback_data="admin_manage_templates")]
    ])


def get_back_to_order_keyboard(order_id):
    """Клавиатура возврата к заказу"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад к заказу", callback_data=f"admin_order_{order_id}")]
    ])


def get_admin_all_orders_keyboard(orders, page=0, total_pages=1):
    """Клавиатура для просмотра всех заказов"""
    keyboard = []

    # Кнопки навигации
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"admin_all_orders_prev_{page - 1}"))

        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="admin_all_orders_page"))

        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"admin_all_orders_next_{page + 1}"))

        keyboard.append(nav_buttons)

    # Кнопки действий для каждого заказа
    for order in orders:
        keyboard.append([
            InlineKeyboardButton(
                f"Управлять заказом #{order['order_id']}",
                callback_data=f"admin_order_{order['order_id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

    return InlineKeyboardMarkup(keyboard)