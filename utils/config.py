"""
Конфиг читается из двух мест (приоритет: переменные окружения > config.ini).
На Railway все значения задаются через Variables в панели проекта.
"""
import configparser
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(BASE_DIR, 'utils', 'config.ini')

# Маппинг ключей конфига → переменные окружения
_ENV_MAP = {
    'bot_token':  'BOT_TOKEN',
    'admin_id':   'ADMIN_ID',
    'chat_id':    'CHAT_ID',
    'api_id':     'API_ID',
    'api_hash':   'API_HASH',
    'two_fa':     'TWO_FA',
    'webapp_url': 'WEBAPP_URL',
}


def create_config():
    cfg = configparser.ConfigParser()
    cfg.add_section('Settings')
    cfg.set('Settings', 'bot_token',  'ТОКЕН_БОТА')
    cfg.set('Settings', 'admin_id',   '0')
    cfg.set('Settings', 'chat_id',    '0')
    cfg.set('Settings', 'api_id',     '0')
    cfg.set('Settings', 'api_hash',   '0')
    cfg.set('Settings', 'two_fa',     '')
    cfg.set('Settings', 'webapp_url', '')
    with open(path, 'w', encoding='utf-8') as f:
        cfg.write(f)


def check_config_file():
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        create_config()
        print('Config created:', path)
        time.sleep(2)


def config(what: str) -> str:
    """Возвращает значение: сначала смотрим env, потом config.ini."""
    env_key = _ENV_MAP.get(what.lower())
    if env_key:
        val = os.environ.get(env_key, '').strip()
        if val:
            return val

    cfg = configparser.ConfigParser()
    cfg.read(path, encoding='utf-8')
    return cfg.get('Settings', what, fallback='').strip()


def edit_config(setting: str, value: str):
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding='utf-8')
    cfg.set('Settings', setting, value)
    with open(path, 'w', encoding='utf-8') as f:
        cfg.write(f)


check_config_file()
