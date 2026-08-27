# 英语听写练习应用 (Dictation Practice)

> 🤖 本项目由 **Claude Code** (Anthropic Claude) 协作开发

## 项目故事

为准备 **KET 考试** 的大孩子设计的智能听写练习工具。核心理念：

1. **语境记忆** - LLM 生成短文，在语境中掌握单词
2. **间隔重复** - 高频错误单词自动加权（至少 3 次）
3. **多感官学习** - 填空提示 + 音标 + 释义 + 例句
4. **即时反馈** - 错误时立即显示正确答案

## 功能特性

- 智能单词录入：粘贴任意文本，LLM 自动提取单词清单
- 填空听写：随机展示部分字母，用户填补空缺
- 错误追踪：自动记录错误单词和错误次数
- 智能复习：高频错误单词自动增加练习频率
- 短文阅读：LLM 生成短文，融入目标单词（~200 词）
- 报表分析：学习数据统计和可视化
- 可观测性：系统日志、LLM 请求追踪

## 跨平台架构

```
dictation-app/
├── platforms/              # 入口层（各平台独立）
│   ├── web/main.py         # Flask Web 启动入口
│   ├── macos/main.py       # Flet macOS 桌面入口
│   └── android/app.py      # Flet Android 入口
├── common/                 # 共享逻辑层
│   ├── config.py           # 配置管理
│   ├── logger.py           # 日志追踪
│   ├── llm/                # LLM 抽象层（providers, passage_generator）
│   ├── services/           # LLM 服务封装
│   └── ui/                 # Flet UI 组件
├── core/                   # 核心算法层
│   └── dictation.py        # 听写会话生成、填空算法
├── storage/                # 数据层
│   └── database.py         # SQLite 数据库操作
├── data/                   # 数据库文件
│   └── dictation.db        # 284 词（KET 核心词汇）
├── templates/              # Flask HTML 模板
├── static/                 # CSS/JS 静态资源
├── tests/                  # 测试套件（191 tests）
├── mobile/                 # Android 构建配置
├── start_web.sh            # Web 启动脚本
└── web_launcher.py         # macOS Web App 启动器
```

## 下载与安装

### macOS 桌面应用

从 [GitHub Releases](https://github.com/backyes/dictation-app/releases) 下载 DMG：

| 包 | 类型 | 大小 |
|---|---|---|
| `DictationPractice.dmg` | Flet 原生桌面 | ~83MB |
| `DictationWeb.dmg` | Flask Web（自动开浏览器） | ~84MB |

安装步骤：
1. 下载 DMG 文件
2. 双击打开，拖入 Applications 文件夹
3. 双击启动

数据库路径：`~/Library/Application Support/DictationPractice/dictation.db`

### Web 版（本地开发）

```bash
git clone https://github.com/backyes/dictation-app.git
cd dictation-app
pip install -r requirements.txt
./start_web.sh
```

访问 http://localhost:5002

### Android APK

从 [GitHub Releases](https://github.com/backyes/dictation-app/releases) 下载 APK：
- `dictationapp-1.0.0-arm64-v8a-debug.apk`（63MB）

## 配置

### LLM API 设置

编辑 `.env` 文件（首次启动也可在 Web 设置页配置）：

```bash
ANTHROPIC_AUTH_TOKEN=your_token_here
ANTHROPIC_BASE_URL=https://api.longcat.chat/anthropic
LLM_MODEL=LongCat-2.0
```

数据库运行时配置通过 Web 设置页面管理（API Key、模型参数等）。

## 使用说明

### 录入单词
- 在首页输入框粘贴单词列表（支持逗号分隔、换行、自然语言）
- 点击"提取单词"预览，确认后添加到词库

### 开始听写
- 系统根据填空提示输入完整单词
- 错误时显示例句和记忆方法

### 短文阅读
- 基于词库单词生成英文短文（~200 词）
- 高频错误词汇优先融入

### 查看报表
- 单词统计、正确/错误清单、练习历史

## 开发指南

### 运行测试

```bash
pytest tests/ -v
# 191 tests, 覆盖核心逻辑、数据库、LLM、Web API
```

### 构建 macOS 应用

```bash
# Flet 桌面版
pyinstaller --windowed --name DictationPractice platforms/macos/flet_main.py

# Web 桌面版
pyinstaller --windowed --name DictationWeb \
  --add-data "templates:templates" \
  --add-data "static:static" \
  web_launcher.py

# 创建 DMG
hdiutil create -volname DictationPractice -srcfolder dist/DictationPractice.app -ov -format UDRW temp.dmg
hdiutil convert temp.dmg -format UDZO -o DictationPractice.dmg
```

### 构建 Android APK

```bash
cd mobile
buildozer android debug
# 输出: mobile/bin/dictationapp-1.0.0-arm64-v8a-debug.apk
```

## 技术栈

| 层 | 技术 |
|---|---|
| Web 后端 | Flask 3.0 + Jinja2 模板 |
| 桌面 UI | Flet 0.21.2 (Flutter-based) |
| 移动端 | Flet Android (Buildozer 构建) |
| 数据库 | SQLite 3 |
| LLM | Anthropic Compatible API (LongCat-2.0) |
| 打包 | PyInstaller (macOS) / Buildozer (Android) |
| 测试 | pytest (191 tests) |

## 数据库结构

### dictation_words_library（单词库）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| word | TEXT | 单词（唯一） |
| meaning | TEXT | 中文释义 |
| example | TEXT | 例句 |
| phonetic | TEXT | 音标 |
| status | TEXT | pending/right/wrong |
| error_count | INTEGER | 错误次数 |

### passages（短文）
### llm_providers（LLM 配置）
### system_settings（系统设置）
### dictation_history（答题记录）

## AI 协作开发

本项目使用 **Claude Code** 协作开发，展示了 AI 在软件开发中的实际应用。

开发统计：
- 开发时长: 约 8 小时
- AI 交互次数: 100+ 轮
- 代码行数: 8000+ 行
- 测试用例: 191 个

## License

MIT License
