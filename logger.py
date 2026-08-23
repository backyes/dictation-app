"""
系统日志模块 - 记录所有 LLM 交互和系统操作
"""
import time
import random
from collections import deque

# 内存日志缓冲区（最近 500 条）
system_logs = deque(maxlen=500)
# LLM 请求追踪（最近 100 条）
llm_traces = deque(maxlen=100)


def add_log(level, module, message, data=None):
    """添加系统日志"""
    log_entry = {
        'id': f"{time.time()}_{random.randint(1000, 9999)}",
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'level': level.upper(),
        'module': module,
        'message': message,
        'data': data
    }
    system_logs.append(log_entry)
    return log_entry


def add_llm_trace(operation, model, success, message, request_data=None, response_data=None, elapsed=None):
    """添加 LLM 请求追踪"""
    trace = {
        'id': f"llm_{time.time()}_{random.randint(1000, 9999)}",
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'operation': operation,
        'model': model,
        'success': success,
        'message': message,
        'elapsed': elapsed,
        'request': request_data,
        'response': response_data
    }
    llm_traces.append(trace)
    return trace


def get_logs(level='all', module='all', limit=200):
    """获取日志列表"""
    filtered = list(system_logs)
    if level != 'all':
        filtered = [l for l in filtered if l['level'].lower() == level.lower()]
    if module != 'all':
        filtered = [l for l in filtered if l['module'] == module]
    return filtered[-limit:]


def get_traces(limit=50):
    """获取 LLM 追踪列表"""
    traces = list(llm_traces)[-limit:]
    traces.reverse()
    return traces


def get_trace_detail(trace_id):
    """获取单条追踪详情"""
    for trace in llm_traces:
        if trace['id'] == trace_id:
            return trace
    return None


def clear_logs():
    """清空日志"""
    system_logs.clear()


def clear_traces():
    """清空追踪"""
    llm_traces.clear()
