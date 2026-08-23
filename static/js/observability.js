/**
 * 系统可观测性模块 - 日志展示、数据库查询、LLM 请求追踪
 */

// ==================== 日志控制台 ====================
class LogConsole {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.maxLines = options.maxLines || 500;
        this.autoScroll = options.autoScroll !== false;
        this.logs = [];
        this.filters = {
            level: 'all',  // all, info, error, warn, debug
            module: 'all'  // all, llm_service, database, api, system
        };
    }

    addLog(level, module, message, data = null) {
        const log = {
            timestamp: new Date().toISOString().substr(11, 12),
            level: level.toUpperCase(),
            module: module,
            message: message,
            data: data
        };
        this.logs.push(log);
        if (this.logs.length > this.maxLines) {
            this.logs.shift();
        }
        this.render(log);
    }

    render(log) {
        if (!this.container) return;

        // 过滤
        if (this.filters.level !== 'all' && log.level.toLowerCase() !== this.filters.level) return;
        if (this.filters.module !== 'all' && log.module !== this.filters.module) return;

        const div = document.createElement('div');
        div.className = `log-line log-${log.level.toLowerCase()}`;

        let html = `<span class="log-time">${log.timestamp}</span>`;
        html += `<span class="log-level log-level-${log.level.toLowerCase()}">${log.level}</span>`;
        html += `<span class="log-module">[${log.module}]</span>`;
        html += `<span class="log-message">${this.escapeHtml(log.message)}</span>`;

        if (log.data) {
            html += `<details class="log-data"><summary>详情</summary><pre>${this.escapeHtml(JSON.stringify(log.data, null, 2))}</pre></details>`;
        }

        div.innerHTML = html;
        this.container.appendChild(div);

        if (this.autoScroll) {
            this.container.scrollTop = this.container.scrollHeight;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    clear() {
        this.logs = [];
        if (this.container) this.container.innerHTML = '';
    }

    setFilter(level, module) {
        this.filters.level = level;
        this.filters.module = module;
        this.refresh();
    }

    refresh() {
        if (!this.container) return;
        this.container.innerHTML = '';
        this.logs.forEach(log => this.render(log));
    }
}

// ==================== 数据库查询 ====================
class DatabaseExplorer {
    constructor() {
        this.tables = ['dictation_words_library', 'llm_providers', 'dictation_history'];
    }

    async query(sql) {
        const response = await fetch('/api/admin/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sql })
        });
        return response.json();
    }

    async getTableInfo(tableName) {
        return this.query(`PRAGMA table_info(${tableName})`);
    }

    async getTableData(tableName, limit = 50, offset = 0) {
        return this.query(`SELECT * FROM ${tableName} LIMIT ${limit} OFFSET ${offset}`);
    }

    async getTableCount(tableName) {
        return this.query(`SELECT COUNT(*) as count FROM ${tableName}`);
    }

    async getRecentHistory(limit = 20) {
        return this.query(`
            SELECT h.*, w.word
            FROM dictation_history h
            JOIN dictation_words_library w ON h.word_id = w.id
            ORDER BY h.created_at DESC
            LIMIT ${limit}
        `);
    }

    async getStatistics() {
        const response = await fetch('/api/statistics');
        return response.json();
    }
}

// ==================== LLM 请求追踪 ====================
class LLMTracer {
    constructor() {
        this.requests = [];
    }

    addRequest(request) {
        this.requests.unshift(request);
        if (this.requests.length > 100) {
            this.requests.pop();
        }
    }

    async getTraceList() {
        const response = await fetch('/api/admin/llm-traces');
        return response.json();
    }

    async getTraceDetail(traceId) {
        const response = await fetch(`/api/admin/llm-traces/${traceId}`);
        return response.json();
    }
}

// ==================== 系统状态监控 ====================
class SystemMonitor {
    constructor() {
        this.metrics = [];
    }

    async getStatus() {
        const response = await fetch('/api/admin/status');
        return response.json();
    }

    async getActiveProvider() {
        const response = await fetch('/api/providers');
        return response.json();
    }

    async testConnection(providerId = null) {
        const url = providerId ? `/api/test/connection/${providerId}` : '/api/test/connection';
        const start = Date.now();
        try {
            const response = await fetch(url);
            const data = await response.json();
            return {
                ...data,
                elapsed: Date.now() - start
            };
        } catch (e) {
            return { success: false, message: e.message, elapsed: Date.now() - start };
        }
    }
}

// ==================== 全局实例 ====================
const logConsole = new LogConsole('logConsole');
const dbExplorer = new DatabaseExplorer();
const llmTracer = new LLMTracer();
const systemMonitor = new SystemMonitor();
