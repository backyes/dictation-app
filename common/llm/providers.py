"""Common LLM provider abstraction"""
import json
import re
import requests
from abc import ABC, abstractmethod
from typing import Any


class LLMResponse:
    """Unified LLM response object"""
    
    def __init__(self, content: str, thinking: str = '', prompt: str = '',
                 raw_response: Any = None, model: str = '', tokens: int = 0):
        self.content = content
        self.thinking = thinking
        self.prompt = prompt
        self.raw_response = raw_response
        self.model = model
        self.tokens = tokens

    def to_dict(self) -> dict:
        return {
            'content': self.content, 'thinking': self.thinking,
            'prompt': self.prompt, 'model': self.model, 'tokens': self.tokens,
        }


class BaseLLMProvider(ABC):
    """LLM provider abstract base class"""
    
    def __init__(self, config: dict):
        self.config = config
    
    @abstractmethod
    def chat(self, messages: list, **kwargs) -> LLMResponse:
        pass
    
    @abstractmethod
    def test_connection(self) -> dict:
        pass
    
    def chat_stream(self, messages: list, **kwargs):
        raise NotImplementedError("Streaming not supported")
    
    def extract_words(self, text: str) -> list:
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
    
    def _parse_words_response(self, text: str) -> list:
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


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude native API"""
    
    def _get_client_kwargs(self) -> dict:
        client_kwargs = {}
        api_key = self.config.get('api_key', '')
        auth_token = self.config.get('auth_token', '')
        base_url = self.config.get('base_url', '')
        
        if auth_token:
            client_kwargs['auth_token'] = auth_token
        elif api_key:
            client_kwargs['api_key'] = api_key
        else:
            raise ValueError("未配置 API 认证信息")
        
        if base_url:
            client_kwargs['base_url'] = base_url
        return client_kwargs
    
    def chat_stream(self, messages: list, **kwargs):
        """Stream chat - yields events: thinking, text, done"""
        import anthropic
        
        client = anthropic.Anthropic(**self._get_client_kwargs())
        
        system_msg = ''
        anthropic_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_msg = msg['content']
            else:
                anthropic_messages.append(msg)
        
        create_kwargs = {
            'model': self.config.get('model', 'claude-sonnet-4-20250514'),
            'max_tokens': int(kwargs.get('max_tokens', self.config.get('max_tokens', 4096))),
            'messages': anthropic_messages,
            'temperature': float(kwargs.get('temperature', 0.7)),
        }
        if system_msg:
            create_kwargs['system'] = system_msg
        
        try:
            with client.messages.stream(**create_kwargs) as stream:
                for event in stream:
                    if event.type == 'content_block_start':
                        if event.content_block.type == 'thinking':
                            yield {'type': 'thinking_start'}
                        elif event.content_block.type == 'text':
                            yield {'type': 'text_start'}
                    elif event.type == 'content_block_delta':
                        delta = event.delta
                        if delta.type == 'thinking_delta':
                            yield {'type': 'thinking', 'content': delta.thinking}
                        elif delta.type == 'text_delta':
                            yield {'type': 'text', 'content': delta.text}
                    elif event.type == 'content_block_stop':
                        pass
                    elif event.type == 'message_stop':
                        tokens = 0
                        if hasattr(stream, 'response') and hasattr(stream.response, 'usage'):
                            tokens = getattr(stream.response.usage, 'output_tokens', 0)
                        yield {'type': 'done', 'tokens': tokens}
        except Exception as e:
            yield {'type': 'error', 'content': str(e)}

    def chat(self, messages: list, **kwargs) -> LLMResponse:
        import anthropic
        client = anthropic.Anthropic(**self._get_client_kwargs())
        
        system_msg = ''
        anthropic_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_msg = msg['content']
            else:
                anthropic_messages.append(msg)
        
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
        
        content = response.content
        thinking_text = ''
        final_text = ''
        
        if not content:
            return LLMResponse(content='', thinking='', prompt=prompt_str,
                              raw_response=response, model=self.config.get('model', ''))
        
        for block in content:
            block_type = getattr(block, 'type', '')
            if block_type == 'thinking' and hasattr(block, 'thinking'):
                thinking_text += block.thinking
            elif block_type == 'text' and hasattr(block, 'text'):
                final_text += block.text
        
        if not final_text and thinking_text:
            final_text = thinking_text
        
        tokens = 0
        if hasattr(response, 'usage'):
            tokens = getattr(response.usage, 'output_tokens', 0)
        
        return LLMResponse(
            content=final_text, thinking=thinking_text, prompt=prompt_str,
            raw_response=response, model=self.config.get('model', ''), tokens=tokens
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
    """OpenAI compatible API"""
    
    def chat(self, messages: list, **kwargs) -> LLMResponse:
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
            content=content, thinking='', prompt=prompt_str,
            raw_response=result, model=self.config.get('model', ''), tokens=tokens
        )
    
    def chat_stream(self, messages: list, **kwargs):
        """Stream chat for OpenAI compatible API"""
        base_url = self.config.get('base_url', 'https://api.openai.com/v1')
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
            'max_tokens': int(kwargs.get('max_tokens', self.config.get('max_tokens', 4096))),
            'temperature': float(kwargs.get('temperature', self.config.get('temperature', 0.7))),
            'stream': True,
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120, stream=True)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data.strip() == '[DONE]':
                            yield {'type': 'done'}
                            return
                        try:
                            chunk = json.loads(data)
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield {'type': 'text', 'content': content}
                        except (json.JSONDecodeError, KeyError):
                            pass
        except Exception as e:
            yield {'type': 'error', 'content': str(e)}
    
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


def create_provider(config: dict) -> BaseLLMProvider:
    """Factory function to create LLM provider"""
    provider_type = config.get('provider_type', 'openai')
    
    if provider_type == 'anthropic':
        return AnthropicProvider(config)
    elif provider_type == 'openai':
        return OpenAIProvider(config)
    else:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
