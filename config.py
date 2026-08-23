import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dictation-app-secret-key')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'dictation.db'))

    # LLM Configuration
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'LongCat-2.0[1m]')
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '1024'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    # 优先使用 ANTHROPIC_BASE_URL，兼容 LLM_BASE_URL
    LLM_BASE_URL = os.environ.get('ANTHROPIC_BASE_URL', os.environ.get('LLM_BASE_URL', ''))
