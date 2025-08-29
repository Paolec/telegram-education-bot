# payment.py - обработка платежей через Robokassa
import hashlib
import urllib.parse
from config import Config


def generate_robokassa_payment_link(order_id, amount, description, user_id):
    """Генерация платежной ссылки для Robokassa"""
    # Формируем параметры для платежа
    login = Config.ROBOKASSA_LOGIN
    password1 = Config.ROBOKASSA_PASSWORD1
    test_mode = Config.ROBOKASSA_TEST_MODE

    # Формируем описание заказа
    inv_desc = f"Заказ #{order_id} - {description}"[:100]  # Ограничение длины описания

    # Формируем подпись
    signature_string = f"{login}:{amount}:{order_id}:{password1}"

    if test_mode == '1':
        signature_string += f":Shp_userId={user_id}:Shp_test=1"
    else:
        signature_string += f":Shp_userId={user_id}"

    signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()

    # Формируем URL
    base_url = "https://auth.robokassa.ru/Merchant/Index.aspx" if test_mode != '1' else "https://auth.robokassa.ru/Merchant/Index.aspx?IsTest=1"

    params = {
        'MerchantLogin': login,
        'OutSum': amount,
        'InvId': order_id,
        'Description': inv_desc,
        'SignatureValue': signature,
        'Shp_userId': user_id
    }

    if test_mode == '1':
        params['IsTest'] = '1'
        params['Shp_test'] = '1'

    payment_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return payment_url


def verify_robokassa_payment(request_params, order_id, amount):
    """Проверка корректности оплаты через Robokassa"""
    password2 = Config.ROBOKASSA_PASSWORD2
    signature = request_params.get('SignatureValue', '')

    # Формируем строку для проверки подписи
    signature_string = f"{amount}:{order_id}:{password2}"

    # Добавляем пользовательские параметры
    for key in sorted(request_params.keys()):
        if key.startswith('Shp_'):
            signature_string += f":{key}={request_params[key]}"

    expected_signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()

    return signature.lower() == expected_signature.lower()