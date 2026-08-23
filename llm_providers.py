"""
LLM 提供商抽象层
支持多种大模型：Anthropic、OpenAI、OpenRouter、Ollama、自定义网关等
所有提供商统一通过 OpenAI-compatible API 或 Anthropic-native API 调用
"""
import json
import re
import requests
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """LLM 提供商抽象基类"""

    def __init__(self, config: dict):
        """
        config 包含:
        - api_key: API 密钥
        - model: 模型名称
        - max_tokens: 最大 token 数
        - temperature: 温度
        - base_url: API 地址
        - provider: 提供商类型
        """
        self.config = config

    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        """
        统一对话接口
        messages: [{"role": "user"|"system"|"assistant", "content": "..."}]
        返回: 模型生成的文本
        """
        pass

    @abstractmethod
    def test_connection(self) -> dict:
        """测试连接是否可用"""
        pass

    def extract_words(self, text: str) -> list:
        """从文本中提取单词清单"""
        prompt = f"""请从以下文本中提取出所有要默写的英语单词清单。

输入文本：
{text}

要求：
1. 只提取英语单词（过滤掉中文、数字、纯符号等）
2. 单词长度至少2个字母
3. 统一转换为小写
4. 去除重复单词
5. 如果文本中没有找到有效单词，返回空列表

请严格按照以下JSON格式返回，不要包含任何其他内容：
{{"words": ["word1", "word2", "word3"]}}"""

        try:
            response = self.chat([{"role": "user", "content": prompt}], temperature=0.1)
            return self._parse_words_response(response)
        except Exception as e:
            raise Exception(f"提取单词失败: {str(e)}")

    def generate_hint(self, word: str) -> dict:
        """为单词生成例句和记忆方法"""
        prompt = f"""请为英语单词 "{word}" 生成学习辅助内容，帮助中学生记忆这个单词。

请严格按照以下JSON格式返回，不要包含任何其他内容：
{{
  "translation": "中文翻译",
  "example": "英文例句（适合中学生水平）",
  "example_translation": "例句的中文翻译",
  "memory_tip": "记忆方法（如词根词缀、联想记忆、谐音记忆等，简洁有趣）"
}}

要求：
1. 例句要简单实用，适合中学生理解
2. 记忆方法要生动有趣，容易记住
3. 所有内容用中文解释（除了example用英文）"""

        try:
            response = self.chat([{"role": "user", "content": prompt}])
            return self._parse_hint_response(response)
        except Exception as e:
            raise Exception(f"生成提示失败: {str(e)}")

    def _parse_words_response(self, text: str) -> list:
        """解析单词提取响应"""
        try:
            result = json.loads(text)
            words = result.get('words', [])
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                result = json.loads(json_match.group())
                words = result.get('words', [])
            else:
                words = re.findall(r'[a-zA-Z]{2,}', text)

        cleaned = []
        seen = set()
        for w in words:
            w = w.strip().lower()
            if re.match(r'^[a-z]{2,}$', w) and w not in seen:
                cleaned.append(w)
                seen.add(w)
        return cleaned

    def _parse_hint_response(self, text: str) -> dict:
        """解析提示生成响应"""
        default = {'translation': '', 'example': '', 'example_translation': '', 'memory_tip': ''}
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                return {**default, 'example': text}
        return {**default, **{k: result.get(k, '') for k in default.keys()}}


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude 原生 API（支持 api_key 和 auth_token 两种认证）"""

    def _get_client_kwargs(self) -> dict:
        """构建客户端参数"""
        client_kwargs = {}

        api_key = self.config.get('api_key', '')
        auth_token = self.config.get('auth_token', '')
        base_url = self.config.get('base_url', '')

        if api_key:
            client_kwargs['api_key'] = api_key
        elif auth_token:
            # LongCat: 使用 auth_token 作为 api_key
            client_kwargs['api_key'] = auth_token

        if base_url:
            client_kwargs['base_url'] = base_url

        return client_kwargs

    def _setup_auth_header(self, client):
        """手动设置 Authorization 头（LongCat 兼容）"""
        auth_token = self.config.get('auth_token', '')
        if auth_token:
            client._client.headers['Authorization'] = f'Bearer {auth_token}'
            client._client.headers['anthropic-version'] = '2023-06-01'

    def chat(self, messages: list, **kwargs) -> str:
        import anthropic

        client = anthropic.Anthropic(**self._get_client_kwargs())
        self._setup_auth_header(client)

        # 转换消息格式（提取 system 消息）
        system_msg = ''
        anthropic_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_msg = msg['content']
            else:
                anthropic_messages.append(msg)

        create_kwargs = {
            'model': self.config.get('model', 'claude-sonnet-4-20250514'),
            'max_tokens': int(self.config.get('max_tokens', 1024)),
            'messages': anthropic_messages
        }
        if system_msg:
            create_kwargs['system'] = system_msg

        response = client.messages.create(**create_kwargs)

        # 处理响应内容（支持 text 和 thinking 类型）
        content = response.content
        if not content:
            return ''

        # 优先获取 text 类型内容
        for block in content:
            if getattr(block, 'type', '') == 'text' and block.text:
                return block.text

        # 如果没有 text 类型，获取 thinking 类型
        for block in content:
            if getattr(block, 'type', '') == 'thinking' and block.thinking:
                return block.thinking

        # 最后尝试任何有 text 属性的块
        for block in content:
            if hasattr(block, 'text') and block.text:
                return block.text

        return str(content[0]) if content else ''

    def test_connection(self) -> dict:
        try:
            import anthropic
            client = anthropic.Anthropic(**self._get_client_kwargs())
            self._setup_auth_header(client)
            response = client.messages.create(
                model=self.config.get('model', 'claude-sonnet-4-20250514'),
                max_tokens=50,
                messages=[{"role": "user", "content": "Reply with OK."}]
            )
            # 提取回复文本（处理 thinking + text 混合响应）
            reply_text = ''
            for block in response.content:
                if getattr(block, 'type', '') == 'text' and block.text:
                    reply_text = block.text.strip()
                    break
            if not reply_text:
                for block in response.content:
                    if getattr(block, 'type', '') == 'thinking' and block.thinking:
                        reply_text = block.thinking.strip()[:50]
                        break
            return {
                'success': True,
                'message': f'连接成功！模型回复: {reply_text}',
                'model': self.config.get('model')
            }
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}', 'model': self.config.get('model', '')}


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 兼容 API（OpenAI、OpenRouter、DeepSeek、Ollama、LongCat 等）"""

    def chat(self, messages: list, **kwargs) -> str:
        import requests

        base_url = self.config.get('base_url', 'https://api.openai.com/v1')
        # 确保 base_url 以 /chat/completions 结尾或拼接
        if not base_url.endswith('/chat/completions'):
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = base_url

        headers = {
            'Authorization': f'Bearer {self.config.get("api_key", "")}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.config.get('model', 'gpt-4o-mini'),
            'messages': messages,
            'max_tokens': int(self.config.get('max_tokens', 1024)),
            'temperature': float(kwargs.get('temperature', self.config.get('temperature', 0.7)))
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']

    def test_connection(self) -> dict:
        try:
            base_url = self.config.get('base_url', 'https://api.openai.com/v1')
            url = f"{base_url.rstrip('/')}/chat/completions"

            headers = {
                'Authorization': f'Bearer {self.config.get("api_key", "")}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': self.config.get('model', 'gpt-4o-mini'),
                'messages': [{"role": "user", "content": "Reply with OK."}],
                'max_tokens': 50
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            reply = result['choices'][0]['message']['content'].strip()
            return {
                'success': True,
                'message': f'连接成功！模型回复: {reply}',
                'model': self.config.get('model')
            }
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}', 'model': self.config.get('model', '')}


# ==================== 提供商工厂 ====================

# 已知提供商的默认配置
PROVIDER_PRESETS = {
    'anthropic': {
        'name': 'Anthropic (Claude)',
        'default_base_url': 'https://api.anthropic.com',
        'default_model': 'claude-sonnet-4-20250514',
        'provider_type': 'anthropic',
        'docs': 'https://console.anthropic.com/'
    },
    'openai': {
        'name': 'OpenAI',
        'default_base_url': 'https://api.openai.com/v1',
        'default_model': 'gpt-4o-mini',
        'provider_type': 'openai',
        'docs': 'https://platform.openai.com/'
    },
    'openrouter': {
        'name': 'OpenRouter',
        'default_base_url': 'https://openrouter.ai/api/v1',
        'default_model': 'anthropic/claude-sonnet-3.5',
        'provider_type': 'openai',  # OpenRouter 使用 OpenAI 兼容格式
        'docs': 'https://openrouter.ai/'
    },
    'deepseek': {
        'name': 'DeepSeek',
        'default_base_url': 'https://api.deepseek.com/v1',
        'default_model': 'deepseek-chat',
        'provider_type': 'openai',
        'docs': 'https://platform.deepseek.com/'
    },
    'longcat': {
        'name': 'LongCat',
        'default_base_url': 'https://api.longcat.chat/openai/v1',
        'default_model': 'LongCat-2.0[1m]',
        'provider_type': 'openai',
        'docs': 'https://api.longcat.chat/'
    },
    'ollama': {
        'name': 'Ollama (本地)',
        'default_base_url': 'http://localhost:11434/v1',
        'default_model': 'llama3',
        'provider_type': 'openai',
        'docs': 'https://ollama.com/'
    },
    'custom': {
        'name': '自定义 (OpenAI 兼容)',
        'default_base_url': '',
        'default_model': '',
        'provider_type': 'openai',
        'docs': ''
    }
}


def create_provider(config: dict) -> BaseLLMProvider:
    """
    根据配置创建对应的 LLM 提供商实例
    config 必须包含 provider_type: 'anthropic' | 'openai'
    """
    provider_type = config.get('provider_type', 'openai')

    if provider_type == 'anthropic':
        return AnthropicProvider(config)
    elif provider_type == 'openai':
        return OpenAIProvider(config)
    else:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
