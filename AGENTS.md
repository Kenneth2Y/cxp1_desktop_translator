# Agent 工作说明

这个项目是一个 Python Tkinter 桌面英汉 / 汉英翻译器，使用 POE 的 OpenAI-compatible API。

## 项目约定

- 主程序是 `main.py`，尽量保持轻量，不引入复杂框架。
- 当前版本号维护在 `main.py` 的 `APP_VERSION`，界面和 README 要同步更新。
- 默认模型是 `gpt-5.3-instant`，但界面里允许用户修改模型名。
- 默认代理是 `socks5://127.0.0.1:10808`，用于配合本机 V2RAYN 等代理工具。
- 代理功能必须保留，但用户可以不勾选代理；程序只在点击“翻译”时联网。
- 模型名称保留手写输入，不做自动拉取 POE 模型列表。
- UI 采用 Windows 深色主题风格：界面字体 `Segoe UI`，正文 `Microsoft YaHei UI`，Debug `Consolas`。
- 右下角 `K.Y.` 是作者标记，保留在界面中。
- `icon.png` 是 Windows 系统托盘图标，需要提交；图片较大也没关系，运行时会缩放到托盘尺寸。
- 窗口关闭按钮隐藏到托盘，底部“退出”和托盘菜单“退出”才是真退出。
- 从 `v1.8.1` 开始，隐藏任务栏的稳定方案是 `ITaskbarList.DeleteTab(hwnd)` 延迟清理；不要改回窗口样式、owner、transient 或 geometry 方案，它们曾导致主窗口只显示小图标或无法恢复。
- 用户配置保存在 `%APPDATA%\cxp1_desktop_translator\config.json`，不要把 API Key 写进源码。
- 翻译历史写入项目目录的 `trans_log.txt`，该文件包含用户内容，必须保持在 `.gitignore` 中。
- Debug 信息可以保留，但不要记录完整 API Key；最多显示 key 是否存在和后四位。
- 项目授权使用 MIT License。

## 开发与验证

- 推荐使用项目虚拟环境运行：

```powershell
.\.venv\Scripts\python.exe main.py
```

- 修改后至少运行：

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py
rg "sk-poe"
```

- 如果需要安装依赖，使用：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Git 与发布习惯

- 只有已经实际运行正常的版本才能 commit 和 push。中间出错、窗口异常、功能半成品等状态，必须先在本地修好，再提交。
- 每完成一个可用版本就 commit 一次；遇到风险较高的修改，先给当前稳定版本打 tag，再继续改。
- 版本号采用简单语义：
  - `1.8.1` 这类补丁版本用于 bug 修复、小幅调整、文档修正。
  - `1.9` 这类小版本用于明确的新功能增加。
  - `2.0` 这类大版本用于界面布局、功能体系或使用方式的明显升级。
- 小幅 bugfix 应基于最近的稳定 tag 修改，例如先保留 `v1.8-stable`，再进入 `v1.8.1`。
- commit message 使用一句简短中文，例如：`增加置顶和字号调整`。
- push 前检查 `git status --short --ignored`，确认只提交源码、文档和依赖声明。
- 不提交 `.venv/`、`__pycache__/`、`trans_log.txt`、本机配置或任何真实 API Key。
- 远程仓库：`https://github.com/Kenneth2Y/cxp1_desktop_translator.git`。
