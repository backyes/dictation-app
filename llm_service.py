"""
LLM 服务封装模块
负责调用大模型 API 进行：
1. 从用户输入文本中提取目标单词清单
2. 为错误单词生成例句和记忆方法
3. 为单词生成中文释义和例句

支持多种提供商：Anthropic、OpenAI、OpenRouter、DeepSeek、LongCat、Ollama 等
"""
import logging
import time
from datetime import datetime
from database import get_active_provider, update_word_meaning, get_words_without_meanings
from llm_providers import create_provider

logger = logging.getLogger(__name__)


def _trace_llm_request(operation, model, success, message, request_data=None, response_data=None, elapsed=None):
    """记录 LLM 请求追踪"""
    try:
        from app import add_llm_trace
        add_llm_trace(operation, model, success, message, request_data, response_data, elapsed)
    except ImportError:
        pass  # 避免循环导入


def get_active_client():
    """获取当前激活的 LLM 提供商客户端"""
    provider_config = get_active_provider()
    if not provider_config:
        raise Exception("没有配置 LLM 提供商，请先在设置页面添加并激活一个提供商")

    # 支持 api_key 或 auth_token 认证
    if not provider_config.get('api_key') and not provider_config.get('auth_token'):
        raise Exception(f"提供商 [{provider_config['name']}] 未设置 API Key 或 Auth Token")

    logger.info(f"使用 LLM 提供商: {provider_config['name']} (model={provider_config.get('model')})")
    return create_provider(provider_config)


def extract_words_from_text(text: str) -> list:
    """
    从用户输入的文本中提取目标单词清单
    支持多种格式：逗号分隔、换行分隔、编号列表等
    """
    logger.info(f"开始提取单词，输入文本长度: {len(text)} 字符")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    # 记录 prompt
    prompt_preview = text[:100] + '...' if len(text) > 100 else text
    logger.info(f"LLM Prompt (extract_words): {prompt_preview}")
    add_log('llm_service', f'提取单词 Prompt: {prompt_preview}')

    try:
        words = client.extract_words(text)
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"提取完成，共 {len(words)} 个单词: {words[:10]}{'...' if len(words) > 10 else ''}")
        _trace_llm_request('extract_words', model, True,
            f"提取 {len(words)} 个单词",
            request_data={'text_length': len(text)},
            response_data={'word_count': len(words), 'words': words[:20]},
            elapsed=elapsed)
        return words
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('extract_words', model, False, str(e),
            request_data={'text_length': len(text)},
            elapsed=elapsed)
        raise


def generate_hint_for_word(word: str) -> dict:
    """
    为错误单词生成例句和记忆方法
    返回: {'example': '...', 'memory_tip': '...', 'translation': '...'}
    """
    logger.info(f"为单词 [{word}] 生成学习提示")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    # 记录 prompt
    logger.info(f"LLM Prompt (generate_hint): word={word}")
    add_log('llm_service', f'生成提示 Prompt: word={word}')

    try:
        hint = client.generate_hint(word)
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"生成提示完成: translation={hint.get('translation', '')[:30]}...")
        _trace_llm_request('generate_hint', model, True,
            f"生成 [{word}] 学习提示",
            request_data={'word': word},
            response_data={'translation': hint.get('translation', '')[:50]},
            elapsed=elapsed)
        return hint
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('generate_hint', model, False, str(e),
            request_data={'word': word},
            elapsed=elapsed)
        raise


def generate_meaning_for_word(word: str) -> dict:
    """
    为单词生成中文释义、例句和音标
    返回: {'meaning': '中文释义', 'example': '例句', 'phonetic': '音标'}
    """
    logger.info(f"为单词 [{word}] 生成释义、例句和音标")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    prompt = f"""请为英语单词 "{word}" 生成：
1. 中文释义（简洁准确）
2. 一个简短的英文例句（适合中学生水平），并将目标单词替换为 "______"（6个下划线）
3. 例句的中文翻译
4. 国际音标（IPA）

请严格按照以下JSON格式返回，不要包含任何其他内容：
{{
  "meaning": "中文释义",
  "example": "英文例句，目标单词用______替代",
  "example_translation": "例句中文翻译",
  "phonetic": "/国际音标/"
}}"""

    try:
        response = client.chat([{"role": "user", "content": prompt}], temperature=0.3)
        import json
        import re

        logger.debug(f"LLM 响应: {response[:200]}...")

        # 解析 JSON
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {'meaning': '', 'example': '', 'example_translation': '', 'phonetic': ''}

        meaning = result.get('meaning', '')
        example = result.get('example', '')
        phonetic = result.get('phonetic', '')
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"生成完成: meaning={meaning[:30]}..., phonetic={phonetic}")

        _trace_llm_request('generate_meaning', model, True,
            f"生成 [{word}] 释义",
            request_data={'word': word},
            response_data={'meaning': meaning[:50], 'phonetic': phonetic},
            elapsed=elapsed)

        return {
            'meaning': meaning,
            'example': example,
            'example_translation': result.get('example_translation', ''),
            'phonetic': phonetic
        }
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('generate_meaning', model, False, str(e),
            request_data={'word': word},
            elapsed=elapsed)
        logger.error(f"生成释义失败: {str(e)}")
        raise Exception(f"生成释义失败: {str(e)}")


def batch_generate_meanings():
    """批量为没有释义的单词生成释义和例句"""
    words = get_words_without_meanings()
    if not words:
        logger.info("没有需要生成释义的单词")
        return {'processed': 0, 'success': 0, 'failed': 0}

    logger.info(f"开始批量生成释义，共 {len(words)} 个单词")
    results = {'processed': len(words), 'success': 0, 'failed': 0}

    for w in words:
        try:
            result = generate_meaning_for_word(w['word'])
            update_word_meaning(w['id'], result['meaning'], result['example'], result.get('phonetic', ''))
            results['success'] += 1
            logger.info(f"  ✅ {w['word']}: {result['meaning'][:20]}..., phonetic={result.get('phonetic', '')}")
        except Exception as e:
            results['failed'] += 1
            logger.error(f"  ❌ {w['word']}: {str(e)}")

    logger.info(f"批量生成完成: 成功 {results['success']}, 失败 {results['failed']}")
    return results


def test_connection(provider_config: dict = None) -> dict:
    """测试 LLM 服务连接"""
    start = time.time()
    try:
        if provider_config is None:
            provider_config = get_active_provider()
            if not provider_config:
                return {'success': False, 'message': '没有配置 LLM 提供商', 'model': ''}

        logger.info(f"测试 LLM 连接: {provider_config.get('name')} (model={provider_config.get('model')})")
        client = create_provider(provider_config)
        result = client.test_connection()
        elapsed = int((time.time() - start) * 1000)

        _trace_llm_request('test_connection', provider_config.get('model', 'unknown'),
            result['success'], result['message'],
            request_data={'provider': provider_config.get('name')},
            elapsed=elapsed)

        if result['success']:
            logger.info(f"连接测试成功: {result['message']}")
        else:
            logger.error(f"连接测试失败: {result['message']}")

        return result
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('test_connection',
            provider_config.get('model', 'unknown') if provider_config else 'unknown',
            False, str(e), elapsed=elapsed)
        logger.error(f"连接测试异常: {str(e)}")
        return {'success': False, 'message': f'连接失败: {str(e)}', 'model': provider_config.get('model', '')}


def generate_passage(words: list, difficulty: str = 'intermediate', custom_prompt: str = None, wrong_words: list = None) -> dict:
    """
    基于词库单词生成短文，帮助学生记忆单词
    - words: 所有可用单词
    - wrong_words: 高频错误词汇（至少30%的单词会从这里选取）
    """
    logger.info(f"生成短文，使用 {len(words)} 个单词")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    # 选择单词：确保至少30%来自高频错误词汇，总共15-20个单词
    max_words = 20
    if wrong_words and len(wrong_words) > 0:
        # 计算至少需要多少个错误词汇（30%）
        min_wrong = max(3, int(max_words * 0.3))
        # 从错误词汇中选取
        selected_wrong = wrong_words[:min_wrong + 2]  # 多选一些备用
        # 从所有词汇中补充剩余
        remaining = [w for w in words if w not in selected_wrong]
        needed_regular = max_words - len(selected_wrong)
        selected_regular = remaining[:needed_regular] if needed_regular > 0 else []
        selected_words = selected_wrong + selected_regular
    else:
        selected_words = words[:max_words] if len(words) > max_words else words

    word_list = ', '.join(selected_words)
    wrong_list = ', '.join(wrong_words[:10]) if wrong_words else ''

    if custom_prompt:
        prompt = custom_prompt.replace('{words}', word_list).replace('{difficulty}', difficulty).replace('{wrong_words}', wrong_list)
    else:
        prompt = f"""# Role
你是一位精通英语教学与故事创作的资深语言专家，擅长通过高联想度、具象化且富有戏剧性的情境短文（Contextual Storytelling），帮助学生高效记忆英语单词。

# Objective
请根据我提供的【目标单词列表】和【高频错误词汇列表】，创作一篇连贯、有趣且逻辑顺畅的英语阅读短文，将所有目标单词自然融入故事中，帮助学生结合语境深化记忆。

# Target Words (必须全部使用)
{word_list}

# 高频错误词汇（请在文中多次复现，加深记忆）
{wrong_list}

# Article Requirements
1. **词汇融入 (100% Coverage & Highlight)**：
   - 必须涵盖"目标单词"列表中的**每一个单词**，不得遗漏或随意替换词形。
   - 高频错误词汇请在文中**多次出现**（至少3次），加深记忆。
   - 文章中出现目标单词时，请使用 **加粗**（**word**）显眼标注。
2. **词汇比例要求**：
   - 高频错误词汇占比至少 **30%**。
   - 每篇短文包含 **15-20 个**目标单词。
3. **篇幅限制 (Length)**：
   - 短文总字数严格控制在 **300 - 400 个英文单词** 之间，保证情节丰富、细节充分。
4. **内容与趣味性 (Storyline & Fun)**：
   - **主题自定/情境匹配**：请观察单词列表的核心主题（如"校园侦探"、"荒岛求生"、"科幻冒险"、"日常奇遇"等），围绕词汇的核心语义设计契合的情景。
   - **戏剧冲突**：情节要生动有趣、有转折或幽默感，避免流水账和为了堆砌词汇而生硬造句。
5. **语言难度 (Language Level)**：
   - 语法结构清晰、自然流畅，适应中初级至中高级英语学习者的阅读水平。

# Output Format
请严格按照以下格式输出，必须包含英文短文和中文翻译：

### 📖 阅读短文 (Story)

**English:**
[300-400词的英文短文，目标单词用**加粗**标记，分段书写]

**Chinese:**
[与英文逐句对应的中文翻译，必须完整翻译整篇文章]

### 📝 重点词汇对照表 (Word Check)
[按单词在文中出现的顺序列出：**单词** - 词性 - 中文释义]

**重要提醒：**
- English 部分必须是纯英文短文
- Chinese 部分必须是与英文对应的中文翻译（逐段对照）
- 不要在中英文部分混入其他语言"""

    # 记录完整 prompt 到日志
    logger.info(f"LLM Prompt (generate_passage):\n{prompt}")
    add_log('llm_service', f'生成短文 Prompt: {len(prompt)} 字符, 单词: {word_list[:100]}...', {'prompt_length': len(prompt), 'words': selected_words[:5]})

    try:
        response = client.chat([{"role": "user", "content": prompt}], temperature=0.8)
        import json
        import re

        logger.debug(f"LLM 响应长度: {len(response)} 字符")

        result = {
            'title': '',
            'title_cn': '',
            'content': '',
            'translation': '',
            'words_used': []
        }

        # 提取短文内容 - 查找 "阅读短文" 或 "Story" 后的内容
        content_patterns = [
            r'(?:📖\s*阅读短文|Story)[^\n]*\n([\s\S]*?)(?=💡|Chinese|中文|📝|Word Check|$)',
            r'#{1,3}[^\n]*(?:Story|阅读)[^\n]*\n([\s\S]*?)(?=#{1,3}|$)',
        ]
        for pattern in content_patterns:
            content_match = re.search(pattern, response, re.IGNORECASE)
            if content_match:
                content = content_match.group(1).strip()
                if len(content) > 100:
                    result['content'] = content
                    break

        # 如果没有匹配到，尝试取最长的段落
        if not result['content']:
            paragraphs = re.split(r'\n\s*\n', response)
            longest = max(paragraphs, key=len, default='')
            if len(longest) > 100:
                result['content'] = longest.strip()

        # 提取中文翻译
        trans_match = re.search(r'(?:💡\s*故事中文大意|Chinese\s*Summary|中文梗概)[^\n]*\n([\s\S]*?)(?=📝|Word Check|$)', response, re.IGNORECASE)
        if trans_match:
            result['translation'] = trans_match.group(1).strip()

        # 提取实际使用的单词
        if result['content']:
            content_lower = result['content'].lower()
            result['words_used'] = [w for w in selected_words if w.lower() in content_lower]

        # 如果没有提取到内容，把整个响应当作内容
        if not result['content']:
            result['content'] = response
            content_lower = response.lower()
            result['words_used'] = [w for w in selected_words if w.lower() in content_lower]

        elapsed = int((time.time() - start) * 1000)
        logger.info(f"短文生成完成: {len(result['content'])} 字符, {len(result['words_used'])} 单词")

        _trace_llm_request('generate_passage', model, True,
            f"生成短文: {len(result['content'])} 字符, {len(result['words_used'])} 单词",
            request_data={'words': selected_words[:5]},
            response_data={'content_length': len(result['content']), 'word_count': len(result['words_used'])},
            elapsed=elapsed)

        return result

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('generate_passage', model, False, str(e),
            request_data={'words': selected_words},
            elapsed=elapsed)
        logger.error(f"短文生成失败: {str(e)}")
        raise Exception(f"短文生成失败: {str(e)}")
