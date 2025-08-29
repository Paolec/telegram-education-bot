import logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, CallbackContext, \
    ConversationHandler, filters

# Импорты из наших модулей
from config import Config
from database import init_db
from utils import error_handler, check_deadlines, handle_wrong_input
from handlers.user_handlers import (
    user_start, user_cancel, user_create_order, user_choose_discipline, user_choose_work_type,
    user_set_custom_work_type, user_handle_deadline, user_handle_budget_type, user_handle_budget,
    user_handle_plagiarism_required, user_handle_plagiarism_system, user_handle_plagiarism_percent,
    user_handle_files, user_handle_upload_done, user_handle_description, user_skip_description,
    user_my_orders, student_approve_order, student_reject_order,
    user_info, user_info_commands, user_info_prices, user_info_requisites,
    user_info_rules, user_info_back,
    USER_SELECTING_ACTION, USER_CHOOSE_DISCIPLINE, USER_CHOOSE_WORK_TYPE, USER_SET_CUSTOM_WORK_TYPE,
    USER_SET_DEADLINE, USER_SELECT_BUDGET_TYPE, USER_SET_BUDGET, USER_SET_PLAGIARISM_REQUIRED,
    USER_CHOOSING_PLAGIARISM_SYSTEM, USER_SET_PLAGIARISM_PERCENT, USER_UPLOAD_FILES, USER_SET_DESCRIPTION,
    USER_VIEWING_ORDERS, USER_INFO_MENU
)
from handlers.admin_handlers import (
    admin_start, admin_cancel, admin_view_orders, admin_orders_by_status, admin_handle_orders_navigation,
    admin_order_details, admin_send_message, admin_handle_message, admin_set_price, admin_handle_price,
    admin_upload_work, admin_handle_completed_file, admin_finish_upload_work, admin_complete_order,
    admin_cancel_order, admin_start_from_query,
    ADMIN_MAIN, ADMIN_VIEW_ORDERS, ADMIN_ORDER_DETAILS, ADMIN_SEND_MESSAGE, ADMIN_SET_PRICE, ADMIN_UPLOAD_WORK
)

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Создаем логгер для действий администратора
admin_logger = logging.getLogger('admin_actions')
admin_handler = logging.FileHandler('admin_actions.log')
admin_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
admin_logger.addHandler(admin_handler)
admin_logger.setLevel(logging.INFO)


def main() -> None:
    """Основная функция запуска бота"""
    # Инициализация базы данных
    init_db()

    # Создаем необходимые директории
    Path(Config.BASE_UPLOAD_FOLDER).mkdir(exist_ok=True, parents=True)
    Path(Config.COMPLETED_FOLDER).mkdir(exist_ok=True, parents=True)

    # Создаем приложение
    application = Application.builder().token(Config.TOKEN).build()

    # Добавляем задачу для проверки дедлайнов в очередь заданий приложения
    application.job_queue.run_repeating(
        check_deadlines,
        interval=86400,  # 24 часа в секундах
        first=10  # Первый запуск через 10 секунд после старта
    )

    # Обработчик диалога для пользователей
    user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', user_start)],
        states={
            USER_SELECTING_ACTION: [
                CallbackQueryHandler(user_create_order, pattern="^user_create_order$"),
                CallbackQueryHandler(user_my_orders, pattern="^user_my_orders$"),
                CallbackQueryHandler(user_info, pattern="^user_info$"),
            ],
            USER_CHOOSE_DISCIPLINE: [
                CallbackQueryHandler(user_choose_discipline, pattern=r"^user_disc_"),
                CallbackQueryHandler(user_start, pattern="^user_back_to_start$")
            ],
            USER_CHOOSE_WORK_TYPE: [
                CallbackQueryHandler(user_choose_work_type, pattern=r"^user_work_"),
                CallbackQueryHandler(user_choose_discipline, pattern="^user_back_to_disciplines$")
            ],
            USER_SET_CUSTOM_WORK_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_set_custom_work_type),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_wrong_input)
            ],
            USER_SET_DEADLINE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_handle_deadline),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_wrong_input)
            ],
            USER_SELECT_BUDGET_TYPE: [
                CallbackQueryHandler(user_handle_budget_type, pattern="^(user_set_budget|user_expert_budget)$")
            ],
            USER_SET_BUDGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_handle_budget),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_wrong_input)
            ],
            USER_SET_PLAGIARISM_REQUIRED: [
                CallbackQueryHandler(user_handle_plagiarism_required,
                                     pattern="^(user_plagiarism_yes|user_plagiarism_no)$")
            ],
            USER_CHOOSING_PLAGIARISM_SYSTEM: [
                CallbackQueryHandler(user_handle_plagiarism_system, pattern=r"^user_plag_sys_")
            ],
            USER_SET_PLAGIARISM_PERCENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_handle_plagiarism_percent),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_wrong_input)
            ],
            USER_UPLOAD_FILES: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, user_handle_files),
                CallbackQueryHandler(user_handle_upload_done, pattern="^user_upload_done$")
            ],
            USER_SET_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_handle_description),
                CallbackQueryHandler(user_skip_description, pattern="^user_skip_description$"),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_wrong_input)
            ],
            USER_VIEWING_ORDERS: [
                CallbackQueryHandler(user_start, pattern="^user_back_to_start$")
            ],
            USER_INFO_MENU: [
                CallbackQueryHandler(user_info_commands, pattern="^user_info_commands$"),
                CallbackQueryHandler(user_info_prices, pattern="^user_info_prices$"),
                CallbackQueryHandler(user_info_requisites, pattern="^user_info_requisites$"),
                CallbackQueryHandler(user_info_rules, pattern="^user_info_rules$"),
                CallbackQueryHandler(user_info_back, pattern="^user_info_back$"),
                CallbackQueryHandler(user_start, pattern="^user_back_to_start$")
            ]
        },
        fallbacks=[
            CommandHandler('cancel', user_cancel),
            CommandHandler('start', user_start)
        ],
    )

    # Обработчик админ-панели
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_start)],
        states={
            ADMIN_MAIN: [
                CallbackQueryHandler(admin_view_orders, pattern="^admin_view_orders$"),
                CallbackQueryHandler(admin_start_from_query, pattern="^admin_back$")
            ],
            ADMIN_VIEW_ORDERS: [
                CallbackQueryHandler(admin_orders_by_status, pattern=r"^admin_orders_"),
                CallbackQueryHandler(admin_handle_orders_navigation, pattern=r"^admin_orders_(prev|next)_"),
                CallbackQueryHandler(admin_order_details, pattern=r"^admin_order_"),
                CallbackQueryHandler(admin_start_from_query, pattern="^admin_back$")
            ],
            ADMIN_ORDER_DETAILS: [
                CallbackQueryHandler(admin_send_message, pattern=r"^admin_send_msg_"),
                CallbackQueryHandler(admin_set_price, pattern=r"^admin_set_price_"),
                CallbackQueryHandler(admin_upload_work, pattern=r"^admin_upload_work_"),
                CallbackQueryHandler(admin_complete_order, pattern=r"^admin_complete_"),
                CallbackQueryHandler(admin_cancel_order, pattern=r"^admin_cancel_"),
                CallbackQueryHandler(admin_view_orders, pattern="^admin_view_orders$")
            ],
            ADMIN_SEND_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handle_message),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_wrong_input)
            ],
            ADMIN_SET_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handle_price),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_wrong_input)
            ],
            ADMIN_UPLOAD_WORK: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, admin_handle_completed_file),
                CommandHandler('done', admin_finish_upload_work)
            ]
        },
        fallbacks=[
            CommandHandler('admin', admin_start),
            CommandHandler('cancel', admin_cancel),
            CommandHandler('done', admin_finish_upload_work)
        ],
    )

    # Добавляем обработчики в приложение
    application.add_handler(user_conv_handler)
    application.add_handler(admin_conv_handler)

    # Добавляем обработчики для кнопок студента
    application.add_handler(CallbackQueryHandler(student_approve_order, pattern="^student_approve_"))
    application.add_handler(CallbackQueryHandler(student_reject_order, pattern="^student_reject_"))

    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    logger.info("Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()