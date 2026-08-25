"""
LLM 提供商抽象层
支持多种大模型：Anthropic、OpenAI、OpenRouter、Ollama、自定义网关等
所有提供商统一通过 OpenAI-compatible API 或 Anthropic-native API 调用
"""
import json
import re
import requests
from abc import ABC, abstractmethod
from typing import Optional, Any


class LLMResponse:
    """统一的 LLM 响应对象"""
    
    def __init__(self, content: str, thinking: str = '', prompt: str = '',
                 raw_response: Any = None, model: str = '', tokens: int = 0):
        self.content = content  # 最终文本内容
        self.thinking = thinking  # thinking 内容（如果有）
        self.prompt = prompt  # 输入 prompt
        self.raw_response = raw_response  # 原始响应对象
        self.model = model  # 使用的模型
        self.tokens = tokens  # token 数量
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'content': self.content,
            'thinking': self.thinking,
            'prompt': self.prompt,
            'model': self.model,
            'tokens': self.tokens,
        }


class BaseLLMProvider(ABC):
    """LLM 提供商抽象基类"""
    
    def __init__(self, config: dict):
        self.config = config
    
    @abstractmethod
    def chat(self, messages: list, **kwargs) -> LLMResponse:
        """
        统一对话接口
        返回: LLMResponse 对象
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
            return self._parse_words_response(response.content)
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
            return self._parse_hint_response(response.content)
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
        
        if auth_token:
            client_kwargs['auth_token'] = auth_token
        elif api_key:
            client_kwargs['api_key'] = api_key
        else:
            raise ValueError("未配置 API 认证信息。请设置 api_key 或 auth_token。")
        
        if base_url:
            client_kwargs['base_url'] = base_url
        
        return client_kwargs
    
    def chat(self, messages: list, **kwargs) -> LLMResponse:
        """调用 Anthropic API"""
        import anthropic
        
        client = anthropic.Anthropic(**self._get_client_kwargs())
        
        # 转换消息格式
        system_msg = ''
        anthropic_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_msg = msg['content']
            else:
                anthropic_messages.append(msg)
        
        # 构建 prompt 字符串（用于 debug）
        prompt_str = '\n'.join([f"[{m['role']}]: {m['content']}" for m in messages])
        
        create_kwargs = {
            'model': self.config.get('model', 'claude-sonnet-4-20250514'),
            'max_tokens': int(kwargs.get('max_tokens', self.config.get('max_tokens', 4096))),
            'messages': anthropic_messages,
            'temperature': float(kwargs.get('temperature', 0.7)),
        }
        if system_msg:
            create_kwargs['system'] = system_msg
        
        response = client.messages.create(**create_kwargs)
        
        # 处理响应内容
        content = response.content
        thinking_text = ''
        final_text = ''
        
        if not content:
            return LLMResponse(content='', thinking='', prompt=prompt_str,
                              raw_response=response, model=self.config.get('model', ''))
        
        # 提取 thinking 和 text
        for block in content:
            block_type = getattr(block, 'type', '')
            if block_type == 'thinking' and hasattr(block, 'thinking'):
                thinking_text += block.thinking
            elif block_type == 'text' and hasattr(block, 'text'):
                final_text += block.text
        
        # 如果没有 text，尝试获取 thinking
        if not final_text and thinking_text:
            final_text = thinking_text
        
        # 获取 token 使用量
        tokens = 0
        if hasattr(response, 'usage'):
            tokens = getattr(response.usage, 'output_tokens', 0)
        
        return LLMResponse(
            content=final_text,
            thinking=thinking_text,
            prompt=prompt_str,
            raw_response=response,
            model=self.config.get('model', ''),
            tokens=tokens
        )
    
    def test_connection(self) -> dict:
        try:
            import anthropic
            client = anthropic.Anthropic(**self._get_client_kwargs())
            response = client.messages.create(
                model=self.config.get('model', 'claude-sonnet-4-20250514'),
                max_tokens=50,
                messages=[{"role": "user", "content": "Reply with OK."}]
            )
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
    
    def chat(self, messages: list, **kwargs) -> LLMResponse:
        """调用 OpenAI 兼容 API"""
        base_url = self.config.get('base_url', 'https://api.openai.com/v1')
        if not base_url.endswith('/chat/completions'):
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = base_url
        
        headers = {
            'Authorization': f'Bearer {self.config.get("api_key", "")}',
            'Content-Type': 'application/json'
        }
        
        prompt_str = '\n'.join([f"[{m['role']}]: {m['content']}" for m in messages])
        
        payload = {
            'model': self.config.get('model', 'gpt-4o-mini'),
            'messages': messages,
            'max_tokens': int(kwargs.get('max_tokens', self.config.get('max_tokens', 4096))),
            'temperature': float(kwargs.get('temperature', self.config.get('temperature', 0.7)))
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        content = result['choices'][0]['message']['content']
        tokens = result.get('usage', {}).get('total_tokens', 0)
        
        return LLMResponse(
            content=content,
            thinking='',  # OpenAI 兼容 API 通常没有 thinking
            prompt=prompt_str,
            raw_response=result,
            model=self.config.get('model', ''),
            tokens=tokens
        )
    
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
        'provider_type': 'openai',
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
    """根据配置创建对应的 LLM 提供商实例"""
    provider_type = config.get('provider_type', 'openai')
    
    if provider_type == 'anthropic':
        return AnthropicProvider(config)
    elif provider_type == 'openai':
        return OpenAIProvider(config)
    else:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
