# 英语听写练习 Web 应用

帮助学生练习英语生词默写的Web应用，支持智能单词提取、填空默写、错误分析和学习提示生成。

## 功能特性

1. **智能单词录入** - 支持任意格式输入文本，通过大模型自动提取单词清单
2. **填空听写** - 随机展示首尾字母/中间字母，用户填补空缺
3. **错误追踪** - 自动记录错误单词和错误次数
4. **智能复习** - 高频错误单词自动增加练习频率（至少3次）
5. **学习提示** - 错误时自动生成例句和记忆方法
6. **报表分析** - 完整的学习数据统计和可视化

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

编辑 `.env` 文件，填入你的 Anthropic API Key：
```
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

### 3. 启动应用

```bash
python app.py
```

访问 http://localhost:5000 即可使用。

## 使用说明

### 录入单词
- 在首页输入框中粘贴单词列表（支持逗号分隔、换行分隔、自然语言等）
- 点击"提取单词"预览，确认后添加到词库

### 开始听写
- 点击"开始听写"按钮
- 系统根据填空提示输入完整单词
- 错误时会显示例句和记忆方法帮助记忆

### 查看报表
- 查看所有单词、正确清单、错误清单
- 查看错误次数统计和练习历史

## 项目结构

```
dictation-app/
├── app.py              # Flask 主程序
├── config.py           # 配置管理
├── database.py         # 数据库操作
├── llm_service.py      # LLM服务封装
├── requirements.txt    # Python依赖
├── .env.example        # 环境变量模板
├── instance/
│   └── dictation.db    # SQLite数据库
├── static/
│   ├── css/style.css   # 样式文件
│   └── js/app.js       # 公共JS
└── templates/
    ├── base.html       # 基础模板
    ├── index.html      # 单词录入页
    ├── dictation.html  # 听写页面
    ├── settings.html   # 设置页面
    ├── test.html       # 测试页面
    └── dashboard.html  # 报表页面
```

## 数据库结构

### dictation_words_library 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| word | TEXT | 单词（唯一） |
| status | TEXT | 状态: pending/right/wrong |
| error_count | INTEGER | 错误次数 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 逻辑分类
- `all_words` = 全表记录
- `right_words` = status='right' 的记录
- `wrong_words` = error_count > 0 的记录

## API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/words/extract | 从文本提取单词 |
| POST | /api/words/add | 添加单词到词库 |
| GET | /api/words | 获取全部单词 |
| GET | /api/words/pending | 获取待默写单词 |
| GET | /api/words/right | 获取正确单词 |
| GET | /api/words/wrong | 获取错误单词 |
| GET | /api/dictation/session | 生成听写会话 |
| POST | /api/dictation/check | 检查答案 |
| GET | /api/settings | 获取LLM设置 |
| POST | /api/settings | 更新LLM设置 |
| GET | /api/test/connection | 测试LLM连接 |
| GET | /api/statistics | 获取统计数据 |
| GET | /api/history | 获取练习历史 |

## 听写算法规则

1. 所有错误词汇至少覆盖1次
2. 错误频率 >=3 次的单词至少出现3次
3. 填空模式随机选择：
   - 短单词(<=4字母)：显示首尾字母
   - 长单词(>4字母)：随机显示首尾/首中尾/分散字母
4. 从未错过 -> 直接标记为right
5. 曾错过但本次正确 -> 标记为right
