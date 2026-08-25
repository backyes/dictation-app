"""
英语听写练习 Web 应用
主程序入口
"""
import logging
import json
import time
from collections import deque
from flask import Flask, render_template, request, jsonify, redirect, url_for
import random
import re
from config import Config

# ==================== 系统日志和追踪 ====================
from logger import add_log, add_llm_trace, get_logs, get_traces, get_trace_detail, clear_logs, clear_traces
from database import (
    init_db, add_words, get_all_words, get_pending_words,
    get_right_words, get_wrong_words, mark_word_correct,
    mark_word_wrong, record_correct_answer, get_statistics,
    get_llm_settings, update_llm_setting, get_recent_history,
    reset_word, reset_all, delete_word, clear_all_words, get_word_history,
    get_all_providers, get_active_provider, get_provider_by_id,
    add_provider, update_provider, delete_provider, set_active_provider,
    add_passage, get_all_passages, get_passage_by_id, delete_passage
)
from llm_service import extract_words_from_text, generate_hint_for_word, test_connection, batch_generate_meanings, generate_meaning_for_word, generate_passage
from llm_providers import PROVIDER_PRESETS

# 确保 instance 目录存在
import os
os.makedirs('instance', exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('instance/app.log', encoding='utf-8')
    ]
)

app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
init_db()


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页 - 单词输入"""
    stats = get_statistics()
    return render_template('index.html', stats=stats)


@app.route('/dictation')
def dictation():
    """听写页面"""
    return render_template('dictation.html')


@app.route('/settings')
def settings():
    """设置页面"""
    llm_settings = get_llm_settings()
    return render_template('settings.html', llm_settings=llm_settings)


@app.route('/test')
def test():
    """测试页面"""
    return render_template('test.html')


@app.route('/passages')
def passages():
    """短文阅读页面"""
    return render_template('passages.html')


@app.route('/observability')
def observability():
    """可观测性页面"""
    return render_template('observability.html')


@app.route('/dashboard')
def dashboard():
    """报表页面"""
    stats = get_statistics()
    all_words = get_all_words()
    right_words = get_right_words()
    wrong_words = get_wrong_words()
    recent_history = get_recent_history(30)
    return render_template('dashboard.html',
                         stats=stats,
                         all_words=all_words,
                         right_words=right_words,
                         wrong_words=wrong_words,
                         recent_history=recent_history)


# ==================== API - 单词管理 ====================

@app.route('/api/words/extract', methods=['POST'])
def api_extract_words():
    """从文本中提取单词"""
    data = request.json
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'success': False, 'message': '请输入文本内容'}), 400

    add_log('info', 'api', f'提取单词请求', {'text_length': len(text)})
    try:
        words = extract_words_from_text(text)
        if not words:
            add_log('warn', 'api', '未提取到有效单词')
            return jsonify({'success': False, 'message': '未能从文本中提取到有效单词'}), 400
        add_log('info', 'api', f'提取完成: {len(words)} 个单词')
        return jsonify({'success': True, 'words': words, 'count': len(words)})
    except Exception as e:
        add_log('error', 'api', f'提取失败: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/words/add', methods=['POST'])
def api_add_words():
    """添加单词到词库"""
    data = request.json
    words = data.get('words', [])

    if not words:
        return jsonify({'success': False, 'message': '单词列表为空'}), 400

    add_log('info', 'api', f'添加 {len(words)} 个单词')
    result = add_words(words)
    add_log('info', 'database', f'添加完成: 新增 {result["added"]}, 重复 {result["duplicate"]}')
    return jsonify({'success': True, **result})


@app.route('/api/words', methods=['GET'])
def api_get_words():
    """获取全部单词"""
    return jsonify({'success': True, 'words': get_all_words()})


@app.route('/api/words/pending', methods=['GET'])
def api_get_pending():
    """获取待默写单词"""
    return jsonify({'success': True, 'words': get_pending_words()})


@app.route('/api/words/right', methods=['GET'])
def api_get_right():
    """获取正确单词"""
    return jsonify({'success': True, 'words': get_right_words()})


@app.route('/api/words/wrong', methods=['GET'])
def api_get_wrong():
    """获取错误单词"""
    return jsonify({'success': True, 'words': get_wrong_words()})


@app.route('/api/words/reset/<int:word_id>', methods=['POST'])
def api_reset_word(word_id):
    """重置单个单词"""
    reset_word(word_id)
    return jsonify({'success': True})


@app.route('/api/words/delete/<int:word_id>', methods=['POST'])
def api_delete_word(word_id):
    """删除单词"""
    delete_word(word_id)
    return jsonify({'success': True})


@app.route('/api/words/clear', methods=['POST'])
def api_clear_words():
    """清空所有单词"""
    clear_all_words()
    return jsonify({'success': True})


# ==================== API - 单词释义生成 ====================

@app.route('/api/words/generate-meanings', methods=['POST'])
def api_generate_meanings():
    """为没有释义的单词批量生成中文释义和例句"""
    add_log('info', 'api', '批量生成释义请求')
    try:
        results = batch_generate_meanings()
        add_log('info', 'api', f'批量生成完成: 成功 {results["success"]}, 失败 {results["failed"]}')
        return jsonify({'success': True, **results})
    except Exception as e:
        add_log('error', 'api', f'批量生成失败: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/words/<int:word_id>/meaning', methods=['POST'])
def api_generate_single_meaning(word_id):
    """为单个单词生成释义"""
    from database import get_db
    conn = get_db()
    word_row = conn.execute('SELECT word FROM dictation_words_library WHERE id = ?', (word_id,)).fetchone()
    conn.close()

    if not word_row:
        return jsonify({'success': False, 'message': '单词不存在'}), 404

    try:
        result = generate_meaning_for_word(word_row['word'])
        update_word_meaning(word_id, result['meaning'], result['example'])
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== API - 短文 ====================

@app.route('/api/passages', methods=['GET'])
def api_get_passages():
    """获取所有短文"""
    passages = get_all_passages()
    return jsonify({'success': True, 'passages': passages})


@app.route('/api/passages/<int:passage_id>', methods=['GET'])
def api_get_passage(passage_id):
    """获取单篇短文"""
    passage = get_passage_by_id(passage_id)
    if passage:
        return jsonify({'success': True, 'passage': passage})
    return jsonify({'success': False, 'message': '短文不存在'}), 404


@app.route('/api/passages/generate', methods=['POST'])
def api_generate_passage():
    """基于词库单词生成短文"""
    data = request.json or {}
    difficulty = data.get('difficulty', 'intermediate')
    custom_prompt = data.get('custom_prompt')
    theme = data.get('theme', '')
    theme_label = data.get('theme_label', '')

    # 获取词库中的单词
    all_words = get_all_words()
    words = [w['word'] for w in all_words if w.get('meaning')]

    # 获取高频错误词汇（错误次数 >= 2）
    wrong_words_data = get_wrong_words()
    wrong_words = [w['word'] for w in wrong_words_data if w.get('error_count', 0) >= 2]

    if len(words) < 3:
        return jsonify({'success': False, 'message': '词库单词不足，请先添加至少3个单词'}), 400

    add_log('info', 'api', f'生成短文请求，使用 {len(words)} 个单词，其中高频错误词汇 {len(wrong_words)} 个，主题: {theme_label}')

    try:
        result = generate_passage(words, difficulty, custom_prompt, wrong_words, theme, theme_label)
        passage_id = add_passage(
            title=result['title'],
            content=result['content'],
            words_used=result['words_used'],
            difficulty=difficulty,
            theme=theme_label
        )
        add_log('info', 'api', f'短文生成完成: {result["title"]}')

        return jsonify({
            'success': True,
            'id': passage_id,
            **result
        })
    except Exception as e:
        add_log('error', 'api', f'短文生成失败: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/passages/<int:passage_id>', methods=['DELETE'])
def api_delete_passage(passage_id):
    """删除短文"""
    delete_passage(passage_id)
    add_log('info', 'api', f'删除短文: {passage_id}')
    return jsonify({'success': True})


@app.route('/api/passages/clear', methods=['POST'])
def api_clear_passages():
    """清空所有短文"""
    conn = get_db()
    conn.execute('DELETE FROM passages')
    conn.commit()
    conn.close()
    add_log('info', 'api', '清空所有短文')
    return jsonify({'success': True})


@app.route('/api/passages/save', methods=['POST'])
def api_save_passage():
    """保存短文到数据库"""
    data = request.json
    try:
        passage_id = add_passage(
            title=data.get('title', '短文'),
            content=data.get('content', ''),
            words_used=data.get('words_used', []),
            difficulty=data.get('difficulty', 'intermediate'),
            theme=data.get('theme', '')
        )
        add_log('info', 'api', f'保存短文: {passage_id}')
        return jsonify({'success': True, 'id': passage_id})
    except Exception as e:
        add_log('error', 'api', f'保存失败: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== API - 听写逻辑 ====================

def generate_clue(word: str) -> dict:
    """
    生成单词线索（填空模式）
    规则：给出首尾字母，或者中间字母，其他用下划线空格
    """
    length = len(word)

    if length <= 2:
        # 短单词：只显示首字母
        clue = word[0] + ' _ ' * (length - 1)
        pattern = 'first_only'
    elif length <= 4:
        # 短单词：显示首尾字母
        clue = word[0] + ' _ ' * (length - 2) + word[-1]
        pattern = 'first_last'
    else:
        # 长单词：随机选择模式
        pattern_type = random.choice(['first_last', 'first_middle_last', 'scattered'])

        if pattern_type == 'first_last':
            # 显示首尾字母
            clue = word[0] + ' _ ' * (length - 2) + word[-1]
            pattern = 'first_last'
        elif pattern_type == 'first_middle_last':
            # 显示首、中间、尾字母
            mid = length // 2
            clue_chars = [' _ '] * length
            clue_chars[0] = word[0]
            clue_chars[mid] = word[mid]
            clue_chars[-1] = word[-1]
            clue = ''.join(clue_chars)
            pattern = 'first_middle_last'
        else:
            # 分散显示约30%的字母
            num_reveal = max(2, length // 3)
            reveal_positions = sorted(random.sample(range(length), num_reveal))
            clue_chars = [' _ '] * length
            for pos in reveal_positions:
                clue_chars[pos] = word[pos]
            clue = ''.join(clue_chars)
            pattern = 'scattered'

    return {
        'clue': clue,
        'length': length,
        'pattern': pattern
    }


@app.route('/api/dictation/session', methods=['GET'])
def api_dictation_session():
    """
    生成一次听写会话
    规则：
    - 对所有错误词汇至少覆盖1次
    - 对于错误频率较高的单词，至少3次
    """
    pending = get_pending_words()
    wrong = get_wrong_words()

    if not pending and not wrong:
        return jsonify({'success': False, 'message': '没有待默写的单词，请先添加单词'})

    session_words = []
    word_ids_added = set()

    # 首先确保所有错误单词至少出现1次
    for w in wrong:
        if w['id'] not in word_ids_added:
            clue_info = generate_clue(w['word'])
            session_words.append({
                'id': w['id'],
                'word': w['word'],
                'clue': clue_info['clue'],
                'length': clue_info['length'],
                'pattern': clue_info['pattern'],
                'meaning': w.get('meaning', ''),
                'example': w.get('example', ''),
                'phonetic': w.get('phonetic', ''),
                'error_count': w['error_count'],
                'priority': 'high' if w['error_count'] >= 3 else 'normal'
            })
            word_ids_added.add(w['id'])

    # 对于错误频率较高的单词(>=3次)，额外增加出现次数（至少3次）
    high_freq_wrong = [w for w in wrong if w['error_count'] >= 3]
    for w in high_freq_wrong:
        extra_count = min(w['error_count'], 3)  # 最多额外3次
        for _ in range(extra_count - 1):  # 已经加了1次
            clue_info = generate_clue(w['word'])
            session_words.append({
                'id': w['id'],
                'word': w['word'],
                'clue': clue_info['clue'],
                'length': clue_info['length'],
                'pattern': clue_info['pattern'],
                'meaning': w.get('meaning', ''),
                'example': w.get('example', ''),
                'phonetic': w.get('phonetic', ''),
                'error_count': w['error_count'],
                'priority': 'high'
            })

    # 添加pending单词
    for w in pending:
        if w['id'] not in word_ids_added:
            clue_info = generate_clue(w['word'])
            session_words.append({
                'id': w['id'],
                'word': w['word'],
                'clue': clue_info['clue'],
                'length': clue_info['length'],
                'pattern': clue_info['pattern'],
                'meaning': w.get('meaning', ''),
                'example': w.get('example', ''),
                'phonetic': w.get('phonetic', ''),
                'error_count': w['error_count'],
                'priority': 'normal'
            })

    # 打乱顺序
    random.shuffle(session_words)

    return jsonify({
        'success': True,
        'session': session_words,
        'total': len(session_words)
    })


@app.route('/api/dictation/check', methods=['POST'])
def api_dictation_check():
    """检查听写答案"""
    data = request.json
    word_id = data.get('word_id')
    user_input = data.get('user_input', '').strip().lower()

    if not word_id:
        return jsonify({'success': False, 'message': '缺少单词ID'}), 400

    # 获取单词
    from database import get_db
    conn = get_db()
    word_row = conn.execute(
        'SELECT * FROM dictation_words_library WHERE id = ?', (word_id,)
    ).fetchone()
    conn.close()

    if not word_row:
        return jsonify({'success': False, 'message': '单词不存在'}), 404

    correct_word = word_row['word']
    is_correct = (user_input == correct_word.lower())

    add_log('info', 'api', f'听写检查: [{correct_word}] 输入=[{user_input}] 结果={"正确" if is_correct else "错误"}')

    if is_correct:
        record_correct_answer(word_id, user_input)
        # 一次性答对：错误次数归零，标记为right，降低听写频率
        mark_word_correct(word_id)
    else:
        mark_word_wrong(word_id, user_input)

    result = {
        'success': True,
        'is_correct': is_correct,
        'correct_word': correct_word,
        'user_input': user_input
    }

    # 如果错误，从数据库读取释义和例句（不调用LLM）
    if not is_correct:
        result['hint'] = {
            'translation': word_row['meaning'] or '',
            'example': word_row['example'] or '',
            'example_translation': '',
            'memory_tip': ''
        }

    return jsonify(result)


# ==================== API - LLM 提供商管理 ====================

@app.route('/api/providers', methods=['GET'])
def api_get_providers():
    """获取所有 LLM 提供商"""
    providers = get_all_providers()
    return jsonify({'success': True, 'providers': providers})


@app.route('/api/providers/presets', methods=['GET'])
def api_get_provider_presets():
    """获取预定义的提供商模板"""
    return jsonify({'success': True, 'presets': PROVIDER_PRESETS})


@app.route('/api/providers', methods=['POST'])
def api_add_provider():
    """添加新的 LLM 提供商"""
    data = request.json
    try:
        provider_id = add_provider(
            name=data.get('name', ''),
            provider_type=data.get('provider_type', 'openai'),
            api_key=data.get('api_key', ''),
            base_url=data.get('base_url', ''),
            model=data.get('model', ''),
            max_tokens=int(data.get('max_tokens', 1024)),
            temperature=float(data.get('temperature', 0.7)),
            is_active=data.get('is_active', False)
        )
        return jsonify({'success': True, 'id': provider_id, 'message': '提供商已添加'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/providers/<int:provider_id>', methods=['PUT'])
def api_update_provider_route(provider_id):
    """更新 LLM 提供商"""
    data = request.json
    try:
        update_provider(provider_id, **data)
        return jsonify({'success': True, 'message': '提供商已更新'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/providers/<int:provider_id>', methods=['DELETE'])
def api_delete_provider_route(provider_id):
    """删除 LLM 提供商"""
    try:
        delete_provider(provider_id)
        return jsonify({'success': True, 'message': '提供商已删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/providers/<int:provider_id>/activate', methods=['POST'])
def api_activate_provider(provider_id):
    """激活指定提供商"""
    try:
        set_active_provider(provider_id)
        return jsonify({'success': True, 'message': '已激活'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/test/connection', methods=['GET'])
@app.route('/api/test/connection/<int:provider_id>', methods=['GET'])
def api_test_connection(provider_id=None):
    """测试 LLM 连接"""
    if provider_id:
        provider = get_provider_by_id(provider_id)
        if not provider:
            return jsonify({'success': False, 'message': '提供商不存在'})
        result = test_connection(provider)
    else:
        result = test_connection()
    return jsonify(result)


# 兼容旧接口
@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """获取当前激活的 LLM 配置（兼容旧接口）"""
    settings = get_llm_settings()
    return jsonify({'success': True, 'settings': settings})


@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    """更新 LLM 设置（兼容旧接口）"""
    data = request.json
    for key, value in data.items():
        update_llm_setting(key, str(value))
    return jsonify({'success': True, 'message': '设置已更新'})


# ==================== API - 统计 ====================

@app.route('/api/statistics', methods=['GET'])
def api_statistics():
    """获取统计数据"""
    return jsonify({'success': True, 'stats': get_statistics()})


@app.route('/api/history', methods=['GET'])
def api_history():
    """获取最近历史"""
    return jsonify({'success': True, 'history': get_recent_history(50)})


@app.route('/api/reset_all', methods=['POST'])
def api_reset_all():
    """重置所有单词状态"""
    reset_all()
    add_log('info', 'system', '重置所有单词状态')
    return jsonify({'success': True, 'message': '已重置所有单词状态'})


# ==================== API - 可观测性 ====================

@app.route('/api/admin/status', methods=['GET'])
def api_admin_status():
    """获取系统完整状态"""
    stats = get_statistics()
    providers = get_all_providers()
    active = get_active_provider()
    logs = get_logs(limit=1)
    return jsonify({
        'success': True,
        'stats': stats,
        'providers': providers,
        'active_provider': active['name'] if active else None,
        'log_count': len(logs),
        'trace_count': len(get_traces())
    })


@app.route('/api/admin/logs', methods=['GET'])
def api_admin_logs():
    """获取系统日志"""
    level = request.args.get('level', 'all')
    module = request.args.get('module', 'all')
    limit = int(request.args.get('limit', 200))

    filtered = get_logs(level=level, module=module, limit=limit)

    return jsonify({'success': True, 'logs': filtered, 'total': len(filtered)})


@app.route('/api/admin/llm-traces', methods=['GET'])
def api_admin_llm_traces():
    """获取 LLM 请求追踪列表"""
    traces = get_traces(limit=50)
    return jsonify({'success': True, 'traces': traces})


@app.route('/api/admin/llm-traces/<trace_id>', methods=['GET'])
def api_admin_llm_trace_detail(trace_id):
    """获取单条 LLM 追踪详情"""
    trace = get_trace_detail(trace_id)
    if trace:
        return jsonify({'success': True, 'trace': trace})
    return jsonify({'success': False, 'message': '追踪记录不存在'})


@app.route('/api/admin/query', methods=['POST'])
def api_admin_query():
    """执行 SQL 查询（只读）"""
    data = request.json
    sql = data.get('sql', '').strip()

    if not sql:
        return jsonify({'success': False, 'message': 'SQL 不能为空'}), 400

    # 安全检查：只允许 SELECT 查询
    if not sql.upper().startswith('SELECT'):
        return jsonify({'success': False, 'message': '只允许 SELECT 查询'}), 403

    try:
        from database import get_db
        conn = get_db()
        cursor = conn.execute(sql)
        columns = [description[0] for description in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()

        results = [dict(zip(columns, row)) for row in rows]
        add_log('info', 'database', f'执行查询: {sql[:50]}...', {'rows': len(results)})

        return jsonify({'success': True, 'results': results, 'columns': columns})
    except Exception as e:
        add_log('error', 'database', f'查询失败: {str(e)}', {'sql': sql})
        return jsonify({'success': False, 'message': str(e)}), 400


# ==================== 启动时自动初始化 ====================

def auto_generate_meanings_on_startup():
    """启动时自动为没有释义的单词生成释义"""
    from database import get_words_without_meanings
    words = get_words_without_meanings()
    if words:
        print(f"发现 {len(words)} 个单词缺少释义，正在后台生成...")
        import threading
        def generate():
            try:
                results = batch_generate_meanings()
                print(f"释义生成完成: 成功 {results['success']}, 失败 {results['failed']}")
            except Exception as e:
                print(f"释义生成失败: {e}")
        thread = threading.Thread(target=generate, daemon=True)
        thread.start()
    else:
        print("所有单词已有释义，无需生成。")


# ==================== 启动 ====================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='英语听写练习 Web 应用')
    parser.add_argument('-p', '--port', type=int, default=5002, help='服务端口号 (默认: 5002)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='服务主机地址 (默认: 0.0.0.0)')
    parser.add_argument('--no-debug', action='store_true', help='关闭调试模式')
    args = parser.parse_args()

    print("=" * 50)
    print("英语听写练习应用已启动")
    print(f"访问: http://localhost:{args.port}")
    print("=" * 50)

    # 启动时自动检查并生成释义
    auto_generate_meanings_on_startup()

    app.run(debug=not args.no_debug, host=args.host, port=args.port)
