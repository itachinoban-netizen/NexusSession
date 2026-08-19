"""
Конфиг читается из переменных окружения (Railway/Render) или config.ini (локально).
"""
import configparser
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(BASE_DIR, 'utils', 'config.ini')

# Маппинг ключей → переменные окружения
_ENV_MAP = {
    'bot_token':  'BOT_TOKEN',
    'admin_id':   'ADMIN_ID',
    'chat_id':    'CHAT_ID',
    'api_id':     'API_ID',
    'api_hash':   'API_HASH',
    'two_fa':     'TWO_FA',
    'webapp_url': 'WEBAPP_URL',
}


def config(what: str) -> str:
    """Сначала смотрим env, потом config.ini."""
    env_key = _ENV_MAP.get(what.lower())
    if env_key:
        val = os.environ.get(env_key, '').strip()
        if val:
            return val

    # Fallback на config.ini (для локального запуска)
    if os.path.exists(path):
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding='utf-8')
        return cfg.get('Settings', what, fallback='').strip()

    return ''


def edit_config(setting: str, value: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg = configparser.ConfigParser()
    if os.path.exists(path):
        cfg.read(path, encoding='utf-8')
    if not cfg.has_section('Settings'):
        cfg.add_section('Settings')
    cfg.set('Settings', setting, value)
    with open(path, 'w', encoding='utf-8') as f:
        cfg.write(f)
