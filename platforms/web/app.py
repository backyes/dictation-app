"""Web platform - Flask UI"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, stream_with_context
from platforms.base import Platform, PlatformConfig
from common.storage.sqlite_storage import get_storage
from common.services.dictation import generate_clue, generate_dictation_session, generate_full_library_session
from common.services.passage_service import generate_passage_stream
from common.services.llm import test_connection, extract_words_from_text, batch_generate_meanings
import os
import json
import threading
import time

# Get the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# In-memory task store for async passage generation
_passage_tasks = {}


class WebPlatform(Platform):
    """Web platform - Flask implementation"""
    
    def __init__(self, config: PlatformConfig = None):
        self.config = config or PlatformConfig()
        self.storage = self.config.storage or get_storage()
        self.app = Flask(
            __name__,
            template_folder=os.path.join(PROJECT_ROOT, 'templates'),
            static_folder=os.path.join(PROJECT_ROOT, 'static')
        )
        self._setup_routes()
    
    def get_name(self) -> str:
        return "Web"
    
    def run(self):
        """Run Flask app"""
        self.app.run(
            debug=self.config.debug,
            host=self.config.host,
            port=self.config.port
        )
    
    def _setup_routes(self):
        """Setup Flask routes"""
        app = self.app
        storage = self.storage
        
        @app.route('/')
        def index():
            stats = storage.get_statistics()
            return render_template('index.html', stats=stats)
        
        @app.route('/passages')
        def passages():
            return render_template('passages.html')
        
        @app.route('/settings')
        def settings():
            return render_template('settings.html')
        
        @app.route('/dashboard')
        def dashboard():
            return render_template('dashboard.html')
        
        @app.route('/dictation')
        def dictation():
            return render_template('dictation.html')
        
        @app.route('/api/statistics')
        def api_statistics():
            return jsonify(storage.get_statistics())
        
        @app.route('/api/words', methods=['GET'])
        def api_get_words():
            return jsonify(storage.get_all_words())
        
        @app.route('/api/words', methods=['POST'])
        def api_add_words():
            data = request.json or {}
            words = data.get('words', [])
            result = storage.add_words(words)
            return jsonify({'success': True, **result})
        
        @app.route('/api/test/connection', methods=['GET'])
        def api_test_connection():
            """Test LLM connection - return detailed info"""
            try:
                provider_config = storage.get_active_provider()
                if not provider_config:
                    return jsonify({'success': False, 'message': '没有配置 LLM 提供商'})
                
                result = test_connection()
                if result.get('success'):
                    result['debug'] = {
                        'provider_name': provider_config.get('name', 'Unknown'),
                        'provider_type': provider_config.get('provider_type', 'unknown'),
                        'model': provider_config.get('model', 'unknown'),
                        'base_url': provider_config.get('base_url', ''),
                        'auth_token': provider_config.get('auth_token', '')[:8] + '...' if provider_config.get('auth_token') else '',
                    }
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})

        @app.route('/api/settings', methods=['GET'])
        def api_get_settings():
            """Get current LLM settings"""
            provider = storage.get_active_provider()
            if not provider:
                return jsonify({'success': True, 'settings': {}})
            return jsonify({
                'success': True,
                'settings': {
                    'auth_token': {'value': provider.get('api_key', '') or provider.get('auth_token', '')},
                    'model': {'value': provider.get('model', '')},
                    'max_tokens': {'value': provider.get('max_tokens', '')},
                    'temperature': {'value': provider.get('temperature', '')},
                    'base_url': {'value': provider.get('base_url', '')},
                }
            })
        
        @app.route('/api/passages', methods=['GET'])
        def api_get_passages():
            passages = storage.get_all_passages()
            return jsonify({'success': True, 'passages': passages})
        
        @app.route('/api/passages/generate/stream', methods=['POST'])
        def api_generate_passage_stream():
            """Generate passage with streaming response (SSE)"""
            data = request.json or {}
            difficulty = data.get('difficulty', 'intermediate')
            
            all_words = storage.get_all_words()
            words = [w['word'] for w in all_words if w.get('meaning')][:8]
            
            wrong_words_data = storage.get_wrong_words()
            wrong_words = [w['word'] for w in wrong_words_data if w.get('error_count', 0) >= 2][:5]
            
            provider_config = storage.get_active_provider()
            if not provider_config:
                return jsonify({'success': False, 'message': '没有配置 LLM 提供商'}), 400
            
            def generate():
                def sse(data):
                    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                for event in generate_passage_stream(
                    words=words,
                    wrong_words=wrong_words,
                    difficulty=difficulty,
                    provider_config=provider_config,
                    storage=storage
                ):
                    yield sse(event)
            
            return Response(stream_with_context(generate()), mimetype='text/event-stream')
        
        @app.route('/api/passages/generate/async', methods=['POST'])
        def api_generate_passage_async():
            """Start async generation - return task ID immediately"""
            return jsonify({'success': True, 'task_id': 'task_sync', 'message': 'Generation started'})
        
        @app.route('/api/passages/generate/status/<task_id>')
        def api_generate_passage_status(task_id):
            """Get generation status - synchronous fallback"""
            data = request.json or {}
            difficulty = data.get('difficulty', 'intermediate')
            
            all_words = storage.get_all_words()
            words = [w['word'] for w in all_words if w.get('meaning')][:8]
            
            wrong_words_data = storage.get_wrong_words()
            wrong_words = [w['word'] for w in wrong_words_data if w.get('error_count', 0) >= 2][:5]
            
            provider_config = storage.get_active_provider()
            
            result_data = None
            for event in generate_passage_stream(
                words=words,
                wrong_words=wrong_words,
                difficulty=difficulty,
                provider_config=provider_config,
                storage=storage
            ):
                if event['type'] == 'done':
                    result_data = event['result']
                    break
                elif event['type'] == 'error':
                    return jsonify({'success': False, 'message': event['message']})
            
            if result_data:
                return jsonify({'success': True, 'status': 'completed', 'result': result_data})
            return jsonify({'success': False, 'message': 'Generation failed'})
        
        @app.route('/api/passages/<int:passage_id>', methods=['DELETE'])
        def api_delete_passage(passage_id):
            """Delete a passage by ID"""
            try:
                conn = storage.get_db()
                conn.execute('DELETE FROM passages WHERE id = ?', (passage_id,))
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': '已删除'})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500
