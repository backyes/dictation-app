import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    配置类 - 环境变量仅作为可选的初始配置
    运行时配置以数据库为准（通过设置页面配置）
    """
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dictation-app-secret-key')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'dictation.db'))

    # LLM Configuration（仅作为默认值，运行时被数据库配置覆盖）
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    ANTHROPIC_AUTH_TOKEN = os.environ.get('ANTHROPIC_AUTH_TOKEN', '')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'LongCat-2.0')
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '1024'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    LLM_BASE_URL = os.environ.get('ANTHROPIC_BASE_URL', os.environ.get('LLM_BASE_URL', ''))
