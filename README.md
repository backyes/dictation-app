# 英语听写练习 Web 应用

> 🤖 本项目由 **Claude Code** (Anthropic Claude) 协作开发

## 项目故事

这个项目源于一个实际需求：给准备 **KET 考试** 的大孩子提高背单词效率。

传统的单词默写方式效率低下，孩子容易遗忘。结合 AI 技术，我们设计了这个智能听写练习应用，通过以下方式提升学习效率：

1. **语境记忆** - 通过例句和短文，让孩子在语境中记忆单词
2. **间隔重复** - 高频错误单词自动增加出现频率
3. **多感官学习** - 音标 + 释义 + 例句 + 填空，全方位刺激记忆
4. **即时反馈** - 错误时立即显示正确答案和记忆方法

## 功能特性

1. **智能单词录入** - 支持任意格式输入文本，通过大模型自动提取单词清单
2. **填空听写** - 随机展示 60% 字母作为提示，用户填补空缺
3. **错误追踪** - 自动记录错误单词和错误次数
4. **智能复习** - 高频错误单词自动增加练习频率（至少3次）
5. **学习提示** - 错误时自动生成例句和记忆方法
6. **短文阅读** - LLM 生成短文，融入目标单词，中英对照阅读
7. **报表分析** - 完整的学习数据统计和可视化
8. **可观测性** - 系统日志、LLM 请求追踪、数据库查询

## 快速开始

### 1. 安装依赖

```bash
cd dictation-app
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 凭证：
```
ANTHROPIC_AUTH_TOKEN=your_token_here
ANTHROPIC_BASE_URL=https://api.longcat.chat/anthropic
LLM_MODEL=LongCat-2.0
```

### 3. 启动应用

```bash
python app.py
```

访问 http://localhost:5002 即可使用。

## 启动参数

```bash
python app.py -p 8080          # 指定端口
python app.py --host 127.0.0.1  # 指定主机
python app.py --no-debug       # 关闭调试模式
```

## 使用说明

### 录入单词
- 在首页输入框中粘贴单词列表（支持逗号分隔、换行分隔、自然语言等）
- 点击"提取单词"预览，确认后添加到词库

### 开始听写
- 点击"开始听写"按钮
- 系统根据填空提示输入完整单词
- 错误时会显示例句和记忆方法帮助记忆

### 短文阅读
- 基于词库单词生成英文短文
- 高频错误词汇优先融入（30%）
- 中英对照阅读

### 查看报表
- 查看所有单词、正确清单、错误清单
- 查看错误次数统计和练习历史

## 项目结构

```
dictation-app/
├── app.py                 # Flask 主程序
├── config.py              # 配置管理
├── database.py            # 数据库操作
├── llm_providers.py       # LLM 提供商抽象层
├── llm_service.py         # LLM 服务封装
├── requirements.txt       # Python 依赖
├── .env.example           # 环境变量模板
├── Procfile               # Render 部署配置
├── render.yaml            # Render Blueprint 配置
├── instance/
│   └── dictation.db       # SQLite 数据库
├── static/
│   ├── css/style.css      # 样式文件
│   └── js/
│       ├── app.js         # 公共 JS
│       └── observability.js # 可观测性模块
├── templates/
│   ├── base.html          # 基础模板
│   ├── index.html         # 单词录入页
│   ├── dictation.html     # 听写页面
│   ├── passages.html      # 短文阅读页
│   ├── settings.html      # 设置页面
│   ├── dashboard.html     # 报表页面
│   ├── observability.html # 可观测性页面
│   └── test.html          # 测试页面
├── tests/
│   ├── test_database.py   # 数据库测试
│   ├── test_dictation.py  # 听写逻辑测试
│   └── test_llm_providers.py # 提供商测试
├── edgeone/               # Tencent EdgeOne 部署配置
└── docs/
    └── ai-interactions/   # AI 交互开发记录
```

## 数据库结构

### dictation_words_library 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| word | TEXT | 单词（唯一） |
| meaning TEXT | 中文释义 |
| example | TEXT | 例句 |
| phonetic | TEXT | 音标 |
| status | TEXT | 状态: pending/right/wrong |
| error_count | INTEGER | 错误次数 |

### passages 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| title | TEXT | 标题 |
| content | TEXT | 短文内容 |
| words_used | TEXT | 使用的单词 |

## 部署

### Render.com
```bash
# 通过 GitHub 自动部署
# Build Command: pip install -r requirements.txt
# Start Command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

### 手动部署
```bash
pip install -r requirements.txt
python app.py -p 8080 --no-debug
```

## AI 协作开发

本项目使用 **Claude Code** 协作开发，展示了 AI 在软件开发中的实际应用。

开发过程中的 AI 交互记录见 [docs/ai-interactions/](docs/ai-interactions/)。

### 开发统计
- 开发时长: 约 4 小时
- AI 交互次数: 50+ 轮
- 代码行数: 6500+ 行
- 测试用例: 61 个

## License

MIT License
