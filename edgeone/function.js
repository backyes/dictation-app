/**
 * Tencent EdgeOne 边缘函数入口
 * 将 Flask 请求转发到边缘函数
 */

// EdgeOne 边缘函数处理入口
export async function handleRequest(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // API 路由
    if (path.startsWith('/api/')) {
        return handleAPI(request, env, path);
    }

    // 静态文件
    if (path.startsWith('/static/')) {
        return handleStatic(request, env, path);
    }

    // 页面路由
    return handlePage(request, env, path);
}

// API 处理
async function handleAPI(request, env, path) {
    // 从环境变量获取后端 API 地址
    const backend = env.BACKEND_API || 'https://your-backend-api.com';

    // 转发请求到后端
    const backendUrl = backend + path;

    try {
        const response = await fetch(backendUrl, {
            method: request.method,
            headers: request.headers,
            body: request.method !== 'GET' ? await request.text() : undefined
        });

        return new Response(await response.text(), {
            status: response.status,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        });
    } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// 静态文件处理
async function handleStatic(request, env, path) {
    // 从环境变量或 CDN 获取静态文件
    const staticCDN = env.STATIC_CDN || 'https://your-cdn.com';
    const response = await fetch(staticCDN + path);

    if (!response.ok) {
        return new Response('Not Found', { status: 404 });
    }

    const contentType = path.endsWith('.css') ? 'text/css' :
        path.endsWith('.js') ? 'application/javascript' :
        'text/plain';

    return new Response(await response.text(), {
        headers: { 'Content-Type': contentType }
    });
}

// 页面处理
async function handlePage(request, env, path) {
    // 返回主页面
    const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>英语听写练习</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <a href="/" class="logo"><span>📝</span>英语听写练习</a>
            <ul class="nav-links">
                <li><a href="/" class="active">📥 单词录入</a></li>
                <li><a href="/dictation">✏️ 开始听写</a></li>
                <li><a href="/passages">📖 短文</a></li>
                <li><a href="/dashboard">📊 报表</a></li>
            </ul>
        </div>
    </nav>
    <main class="main-content">
        <div class="container">
            <h2>正在加载...</h2>
            <p>请稍候，应用正在初始化。</p>
        </div>
    </main>
    <script src="/static/js/app.js"></script>
</body>
</html>`;

    return new Response(html, {
        headers: { 'Content-Type': 'text/html;charset=UTF-8' }
    });
}
