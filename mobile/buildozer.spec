[app]
title = Dictation Practice
package.name = dictationapp
package.domain = com.backyes

# Source directory is the project root so all packages are importable
source.dir = ..
source.include_exts = py,png,jpg,kv,atlas,ttf,woff,woff2,json,html,css,js
source.exclude_dirs = .git,__pycache__,node_modules,.venv,venv,tests,demo,instance

version = 1.0.0

# Requirements for Android mobile build
# flet: UI framework
# anthropic: LLM SDK
# requests: HTTP client (used by anthropic and providers)
# python-dotenv: environment config
requirements = python3,flet==0.21.2,anthropic==0.40.0,requests==2.31.0,python-dotenv==1.0.0,charset_normalizer,certifi,idna,urllib3,anyio,distro,httpx,httpx-socks,httpcore,pysocks,sniffio,typing_extensions,markdown,pygments,websocket_client,oauthlib,packaging,pyyaml,qrcode,arrow,types_python_dateutil,sh

orientation = portrait
fullscreen = 0

# Android permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,WAKE_LOCK,FOREGROUND_SERVICE,POST_NOTIFICATIONS

android.api = 34
android.minapi = 21
android.archs = arm64-v8a
android.allow_backup = True

# Use gradle for dependency resolution
# android.gradle_dependencies = 

# Enable AndroidX
android.enable_androidx = True

# Build format (apk is simpler than aab)
android.build_tools = 34.0.0

# Icon and presplash (will use defaults if not found)
icon.filename = %(source.dir)s/mobile/assets/icon.png
presplash.filename = %(source.dir)s/mobile/assets/presplash.png

# Logging
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1