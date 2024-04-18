import logging
import time
from http import HTTPStatus

import requests
import telegram

from constants import (
    ENDPOINT,
    HEADERS,
    HOMEWORK_VERDICTS,
    PRACTICUM_TOKEN,
    RETRY_PERIOD,
    TELEGRAM_CHAT_ID,
    TELEGRAM_TOKEN,
    WEEK
)
from exceptions import (
    EndPointResponseError,
    MissingTokenError,
    ListIsEmptyError
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка токенов.Если токены верны возвращает True, если нет False."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в телеграмм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение отправлено: {message}')
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка отправки сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Запрос к API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise EndPointResponseError(
                f'Ошибка доступа {ENDPOINT}, Код ошибки:{response.status_code}'
            )
    except requests.RequestException as requesterror:
        logger.error(f'Произошла ошибка при запросе к API: {requesterror}')
    try:
        return response.json()
    except ValueError:
        raise ValueError('Некорректные типы данных')


def check_response(response):
    """Проверка запросов API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь.')
    try:
        home_works = response['homeworks']
    except KeyError:
        raise KeyError('Ключ "homeworks" не найден.')
    if not isinstance(home_works, list):
        raise TypeError('Ответ API не список.')


def parse_status(homework):
    """Получение статусов домашних заданий."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise ValueError(f'Отсутствует или пустое поле: {homework_name}')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует переменная окружения.')
        raise MissingTokenError

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - WEEK

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response['homeworks'][-1]
            if homework is None:
                logger.error('Передан пустой список.')
                raise ListIsEmptyError
            current_date = response['current_date']
            timestamp = current_date
            message = parse_status(homework)
            send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('Работа бота звершена клавишами CTRL + C')
