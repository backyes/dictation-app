import sqlite3
import os
from datetime import datetime
from config import Config


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库表"""
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # 单词库主表 - dictation_words_library
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictation_words_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            meaning TEXT DEFAULT '',
            example TEXT DEFAULT '',
            phonetic TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            error_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 短文表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS passages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            words_used TEXT DEFAULT '',
            difficulty TEXT DEFAULT 'intermediate',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 系统配置表（存储 API Key 等敏感信息）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            description TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 初始化默认配置
    default_settings = [
        ('api_key', '', 'Anthropic API Key'),
        ('auth_token', '', 'Anthropic Auth Token (LongCat)'),
        ('base_url', 'https://api.longcat.chat/anthropic', 'API Base URL'),
        ('model', 'LongCat-2.0', 'LLM 模型名称'),
        ('max_tokens', '1024', '最大 Token 数'),
        ('temperature', '0.7', '温度参数'),
    ]
    for key, value, desc in default_settings:
        cursor.execute(
            'INSERT OR IGNORE INTO system_settings (key, value, description) VALUES (?, ?, ?)',
            (key, value, desc)
        )

    # LLM 提供商配置表（支持多提供商）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider_type TEXT NOT NULL DEFAULT 'openai',
            api_key TEXT DEFAULT '',
            auth_token TEXT DEFAULT '',
            base_url TEXT DEFAULT '',
            model TEXT DEFAULT '',
            max_tokens INTEGER DEFAULT 1024,
            temperature REAL DEFAULT 0.7,
            is_active INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 默写历史记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            user_input TEXT,
            is_correct INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES dictation_words_library(id)
        )
    ''')

    # 初始化默认提供商（仅在表为空时）
    cursor.execute('SELECT COUNT(*) FROM llm_providers')
    if cursor.fetchone()[0] == 0:
        default_providers = [
            ('Anthropic Claude', 'anthropic', Config.ANTHROPIC_API_KEY,
             'https://api.anthropic.com', 'claude-sonnet-4-20250514', 1024, 0.7, 0),
            ('LongCat', 'openai', Config.ANTHROPIC_API_KEY,
             'https://api.longcat.chat/openai/v1', 'LongCat-2.0[1m]', 1024, 0.7, 1),
        ]
        for p in default_providers:
            cursor.execute('''
                INSERT INTO llm_providers
                (name, provider_type, api_key, base_url, model, max_tokens, temperature, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', p)

    conn.commit()
    conn.close()


# ==================== dictation_words_library 操作 ====================

def add_words(words: list) -> dict:
    """批量添加单词，返回新增和重复的数量"""
    import re
    conn = get_db()
    added, duplicate = 0, 0
    for word in words:
        word = word.strip().lower()
        # 过滤空字符串和单字母
        if not word or len(word) < 2:
            continue
        # 只保留纯字母单词
        if not re.match(r'^[a-z]+$', word):
            continue
        try:
            conn.execute(
                'INSERT INTO dictation_words_library (word, status) VALUES (?, ?)',
                (word, 'pending')
            )
            added += 1
        except sqlite3.IntegrityError:
            duplicate += 1
    conn.commit()
    conn.close()
    return {'added': added, 'duplicate': duplicate}


def update_word_meaning(word_id: int, meaning: str, example: str = '', phonetic: str = ''):
    """更新单词的中文释义、例句和音标"""
    conn = get_db()
    conn.execute(
        'UPDATE dictation_words_library SET meaning = ?, example = ?, phonetic = ?, updated_at = ? WHERE id = ?',
        (meaning, example, phonetic, datetime.now().isoformat(), word_id)
    )
    conn.commit()
    conn.close()


def get_words_without_meanings() -> list:
    """获取还没有释义的单词"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM dictation_words_library WHERE meaning = '' OR meaning IS NULL"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_words() -> list:
    """获取全部单词 ditation_words_library.all_words"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM dictation_words_library ORDER BY id'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_words() -> list:
    """获取待默写单词（未正确完成的）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM dictation_words_library WHERE status != 'right' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_right_words() -> list:
    """获取已正确默写的单词 ditation_words_library.right_words"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM dictation_words_library WHERE status = 'right' ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_wrong_words() -> list:
    """获取错误单词 ditation_words_library.wrong_words"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM dictation_words_library WHERE error_count > 0 ORDER BY error_count DESC, updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_word_correct(word_id: int):
    """标记单词为正确，错误次数归零"""
    conn = get_db()
    conn.execute(
        "UPDATE dictation_words_library SET status = 'right', error_count = 0, updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), word_id)
    )
    conn.commit()
    conn.close()


def mark_word_wrong(word_id: int, user_input: str = ''):
    """标记单词为错误，错误次数+1"""
    conn = get_db()
    conn.execute(
        """UPDATE dictation_words_library
           SET status = 'wrong', error_count = error_count + 1, updated_at = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), word_id)
    )
    conn.execute(
        'INSERT INTO dictation_history (word_id, user_input, is_correct) VALUES (?, ?, 0)',
        (word_id, user_input)
    )
    conn.commit()
    conn.close()


def record_correct_answer(word_id: int, user_input: str = ''):
    """记录一次正确回答（但不一定标记为永久正确）"""
    conn = get_db()
    conn.execute(
        'INSERT INTO dictation_history (word_id, user_input, is_correct) VALUES (?, ?, 1)',
        (word_id, user_input)
    )
    conn.commit()
    conn.close()


def reset_word(word_id: int):
    """重置单词状态"""
    conn = get_db()
    conn.execute(
        "UPDATE dictation_words_library SET status = 'pending', error_count = 0, updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), word_id)
    )
    conn.commit()
    conn.close()


def reset_all():
    """重置所有单词"""
    conn = get_db()
    conn.execute("UPDATE dictation_words_library SET status = 'pending', error_count = 0")
    conn.commit()
    conn.close()


def delete_word(word_id: int):
    """删除单词"""
    conn = get_db()
    conn.execute('DELETE FROM dictation_history WHERE word_id = ?', (word_id,))
    conn.execute('DELETE FROM dictation_words_library WHERE id = ?', (word_id,))
    conn.commit()
    conn.close()


def clear_all_words():
    """清空所有单词"""
    conn = get_db()
    conn.execute('DELETE FROM dictation_history')
    conn.execute('DELETE FROM dictation_words_library')
    conn.commit()
    conn.close()


# ==================== 短文操作 ====================

def add_passage(title: str, content: str, words_used: list, difficulty: str = 'intermediate') -> int:
    """添加短文到数据库"""
    import re
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO passages (title, content, words_used, difficulty) VALUES (?, ?, ?, ?)',
        (title, content, ','.join(words_used), difficulty)
    )
    passage_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return passage_id


def get_all_passages() -> list:
    """获取所有短文"""
    conn = get_db()
    rows = conn.execute('SELECT * FROM passages ORDER BY created_at DESC').fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['words_list'] = [w for w in d['words_used'].split(',') if w]
        result.append(d)
    return result


def get_passage_by_id(passage_id: int) -> dict:
    """根据ID获取短文"""
    conn = get_db()
    row = conn.execute('SELECT * FROM passages WHERE id = ?', (passage_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['words_list'] = [w for w in d['words_used'].split(',') if w]
        return d
    return None


def delete_passage(passage_id: int):
    """删除短文"""
    conn = get_db()
    conn.execute('DELETE FROM passages WHERE id = ?', (passage_id,))
    conn.commit()
    conn.close()


def get_statistics() -> dict:
    """获取统计数据"""
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM dictation_words_library').fetchone()[0]
    right = conn.execute("SELECT COUNT(*) FROM dictation_words_library WHERE status = 'right'").fetchone()[0]
    wrong = conn.execute("SELECT COUNT(*) FROM dictation_words_library WHERE error_count > 0").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM dictation_words_library WHERE status = 'pending'").fetchone()[0]
    total_errors = conn.execute('SELECT COALESCE(SUM(error_count), 0) FROM dictation_words_library').fetchone()[0]
    total_attempts = conn.execute('SELECT COUNT(*) FROM dictation_history').fetchone()[0]
    correct_attempts = conn.execute('SELECT COUNT(*) FROM dictation_history WHERE is_correct = 1').fetchone()[0]
    conn.close()
    return {
        'total': total,
        'right': right,
        'wrong': wrong,
        'pending': pending,
        'total_errors': total_errors,
        'total_attempts': total_attempts,
        'correct_attempts': correct_attempts,
        'accuracy': round(correct_attempts / total_attempts * 100, 1) if total_attempts > 0 else 0
    }


# ==================== LLM 提供商操作 ====================

def get_all_providers() -> list:
    """获取所有 LLM 提供商配置"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM llm_providers ORDER BY is_active DESC, id ASC'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_provider() -> dict:
    """获取当前激活的 LLM 提供商配置"""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1'
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_provider_by_id(provider_id: int) -> dict:
    """根据 ID 获取提供商配置"""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM llm_providers WHERE id = ?', (provider_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_provider(name: str, provider_type: str, api_key: str = '',
                 base_url: str = '', model: str = '', max_tokens: int = 1024,
                 temperature: float = 0.7, is_active: bool = False,
                 auth_token: str = '') -> int:
    """添加新的 LLM 提供商"""
    conn = get_db()
    # 如果设为激活，先取消其他激活状态
    if is_active:
        conn.execute('UPDATE llm_providers SET is_active = 0')
    cursor = conn.execute('''
        INSERT INTO llm_providers
        (name, provider_type, api_key, auth_token, base_url, model, max_tokens, temperature, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, provider_type, api_key, auth_token, base_url, model, max_tokens, temperature,
          1 if is_active else 0, datetime.now().isoformat()))
    provider_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return provider_id


def update_provider(provider_id: int, **kwargs):
    """更新 LLM 提供商配置"""
    allowed_fields = {'name', 'provider_type', 'api_key', 'auth_token', 'base_url', 'model',
                      'max_tokens', 'temperature', 'is_active'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return

    # 如果设为激活，先取消其他激活状态
    if updates.get('is_active'):
        conn = get_db()
        conn.execute('UPDATE llm_providers SET is_active = 0 WHERE id != ?', (provider_id,))
        conn.commit()
        conn.close()

    set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
    set_clause += ', updated_at = ?'
    values = list(updates.values()) + [datetime.now().isoformat(), provider_id]

    conn = get_db()
    conn.execute(f'UPDATE llm_providers SET {set_clause} WHERE id = ?', values)
    conn.commit()
    conn.close()


def delete_provider(provider_id: int):
    """删除 LLM 提供商"""
    conn = get_db()
    conn.execute('DELETE FROM llm_providers WHERE id = ?', (provider_id,))
    conn.commit()
    conn.close()


def set_active_provider(provider_id: int):
    """设置激活的提供商"""
    conn = get_db()
    conn.execute('UPDATE llm_providers SET is_active = 0')
    conn.execute(
        'UPDATE llm_providers SET is_active = 1, updated_at = ? WHERE id = ?',
        (datetime.now().isoformat(), provider_id)
    )
    conn.commit()
    conn.close()


# 兼容旧接口（过渡期使用）
def get_llm_settings() -> dict:
    """获取当前激活的 LLM 配置（兼容旧接口）"""
    provider = get_active_provider()
    if not provider:
        return {}
    return {
        'api_key': {'value': provider.get('api_key', ''), 'description': 'API Key'},
        'model': {'value': provider.get('model', ''), 'description': '模型名称'},
        'max_tokens': {'value': str(provider.get('max_tokens', 1024)), 'description': '最大Token数'},
        'temperature': {'value': str(provider.get('temperature', 0.7)), 'description': '温度参数'},
        'base_url': {'value': provider.get('base_url', ''), 'description': 'API Base URL'},
        'provider_type': {'value': provider.get('provider_type', 'openai'), 'description': '提供商类型'},
    }


def update_llm_setting(key: str, value: str):
    """更新 LLM 设置（兼容旧接口，更新当前激活的提供商）"""
    provider = get_active_provider()
    if not provider:
        return
    field_map = {
        'api_key': 'api_key',
        'auth_token': 'auth_token',
        'model': 'model',
        'max_tokens': 'max_tokens',
        'temperature': 'temperature',
        'base_url': 'base_url',
        'provider_type': 'provider_type',
    }
    if key in field_map:
        update_provider(provider['id'], **{field_map[key]: value})


# ==================== 历史记录操作 ====================

def get_word_history(word_id: int) -> list:
    """获取单词的默写历史"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM dictation_history WHERE word_id = ? ORDER BY created_at DESC',
        (word_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_history(limit: int = 50) -> list:
    """获取最近的默写历史"""
    conn = get_db()
    rows = conn.execute('''
        SELECT h.*, w.word FROM dictation_history h
        JOIN dictation_words_library w ON h.word_id = w.id
        ORDER BY h.created_at DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
