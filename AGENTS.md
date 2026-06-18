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
- Windows 任务栏隐藏使用 Windows `ITaskbarList.DeleteTab(hwnd)`，不要使用 `-toolwindow`、`WS_EX_TOOLWINDOW`、hidden owner/transient 或 `GWLP_HWNDPARENT`，它们会把主界面压成只有关闭按钮/图标的小窗口。
- 用户配置保存在 `%APPDATA%\cxp1_desktop_translator\config.json`，不要把 API Key 写进源码。
- `window_geometry` 可能被实验性托盘/窗口样式保存成极小尺寸；必须通过最小宽高校验，异常时回落到 `DEFAULT_GEOMETRY`。
- 窗口位置通过 `<Configure>` 延迟保存，支持拖到多显示器后自动记忆；不要只依赖退出时保存。
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

- 每完成一个可用版本就 commit 一次。
- commit message 使用一句简短中文，例如：`增加置顶和字号调整`。
- push 前检查 `git status --short --ignored`，确认只提交源码、文档和依赖声明。
- 不提交 `.venv/`、`__pycache__/`、`trans_log.txt`、本机配置或任何真实 API Key。
- 远程仓库：`https://github.com/Kenneth2Y/cxp1_desktop_translator.git`。
