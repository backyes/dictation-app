# Render.com 部署指南

## 快速部署

### 方式一：通过 Blueprint 部署（推荐）

1. 将代码推送到 GitHub
2. 在 Render 控制台点击 **New +** → **Blueprint**
3. 选择 GitHub 仓库 `backyes/dictation-app`
4. Render 会自动读取 `render.yaml` 配置

### 方式二：手动部署

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 **New +** → **Web Service**
3. 选择 GitHub 仓库
4. 配置：
   - **Name**: `dictation-app`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn platforms.web.app:app --bind 0.0.0.0:$PORT --workers 2`

## 环境变量配置

在 Render 控制台 → **Environment** 添加：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ANTHROPIC_AUTH_TOKEN` | LongCat API Token | `your_token` |
| `ANTHROPIC_BASE_URL` | API 地址 | `https://api.longcat.chat/anthropic` |
| `LLM_MODEL` | 模型名称 | `LongCat-2.0` |
| `SECRET_KEY` | Flask 密钥 | 随机生成 |
| `PYTHON_VERSION` | Python 版本 | `3.11.15` |
| `DATABASE_PATH` | 数据库路径 | `/opt/render/project/src/instance/dictation.db` |

## 持久化存储

Render 使用 `disk` 配置持久化 SQLite 数据库：
- **Mount Path**: `/opt/render/project/src/instance`
- **Size**: 1 GB

> ⚠️ 注意：Render 免费版磁盘会在服务休眠后重置，建议使用 PostgreSQL 数据库。

## 使用 PostgreSQL（推荐生产环境）

1. 在 Render 创建 PostgreSQL 数据库
2. 获取 Internal Database URL
3. 修改 `config.py` 使用 PostgreSQL

## 部署验证

部署完成后访问：
```
https://dictation-app.onrender.com
```

## 常见问题

**Q: 服务休眠怎么办？**
A: Render 免费版 15 分钟无请求会休眠，首次访问需要等待冷启动。

**Q: 数据库数据丢失？**
A: 免费版磁盘不保证持久化，建议升级到付费版或使用 PostgreSQL。
