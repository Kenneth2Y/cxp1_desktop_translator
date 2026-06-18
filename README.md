# 英汉 / 汉英桌面翻译器

一个轻量的 Python Tkinter 桌面翻译小工具。输入英文输出中文，输入中文输出英文。默认使用 POE 的 OpenAI-compatible Chat Completions API 和 `gpt-5.3-instant`。

当前版本：`v2.3`

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果你已经激活了自己的 Python 环境，也可以直接运行：

```powershell
python -m pip install -r requirements.txt
```

## 运行

```powershell
.\.venv\Scripts\python.exe main.py
```

首次运行后，在界面里填写 POE API Key，点击“应用”保存。API Key 会保存到本机用户配置目录：

```text
%APPDATA%\cxp1_desktop_translator\config.json
```

不要把真实 API Key 写进源码或提交到 GitHub。

## 双击启动

项目里提供了 `start_translator.vbs`，双击它可以无黑色命令行窗口启动程序。它会使用项目虚拟环境里的：

```text
.venv\Scripts\pythonw.exe
```

如果想开机自启动，可以给 `start_translator.vbs` 创建快捷方式，然后把快捷方式放进 Windows 启动文件夹。启动文件夹可通过运行：

```text
shell:startup
```

打开。

## 界面功能

- “置顶”可以让窗口保持在其他窗口前面，再次取消勾选即可恢复。
- 原文标题旁的“清空”只清空原文，保留当前译文用于对照或避免误操作。
- 译文标题旁的“复制”会把译文复制到系统剪贴板，方便粘贴到回帖、邮件或聊天窗口。
- “字体+”和“字体-”会同步调整界面、按钮、输入框、译文框和 Debug 区域的字号。
- 原文、译文和 Debug 区域都有竖向滚动条；文本较长时也可以使用鼠标滚轮或方向键浏览。
- “退出”按钮会保存窗口位置、字号、置顶状态、代理设置等配置后关闭程序。
- 程序会使用 `icon.png` 显示在 Windows 系统托盘，并尽量从任务栏隐藏；右键托盘图标可显示/隐藏或退出。
- 界面默认使用接近 Windows 记事本的深色主题，适合深色桌面环境。
- Windows 下界面字体使用 `Segoe UI`，原文/译文使用 `Microsoft YaHei UI`，Debug 使用 `Consolas`。这些都是 Windows 常见自带字体，便于兼容。
- 右下角 `K.Y.` 是作者标记，写在界面中。

## 代理

界面默认启用 SOCKS 代理：

```text
socks5://127.0.0.1:10808
```

如果你使用 V2RAYN 或其他本机代理，可以在界面中修改代理地址，或取消勾选“使用代理”直接连接。

模型名称保留手写输入。POE 支持的模型可以直接填入模型框并点击“应用”；如果模型名不可用，Debug 区域会显示 API 或连接错误，便于排查。

## Debug

Debug 区域默认开启，会显示类似下面的故障代码：

```text
ERROR missing_api_key
ERROR connection_failed proxy_or_network
ERROR auth_failed check_api_key
ERROR api_error status=...
```

Debug 不会记录完整 API Key，只会显示是否存在和末尾四位。

## 翻译历史

每次成功翻译都会追加写入项目目录下的 `trans_log.txt`，包含时间戳、模型名、原文、译文。界面里的“历史”按钮会用系统默认文本编辑器打开该文件。

`trans_log.txt` 已经加入 `.gitignore`，避免把个人翻译内容提交到公开仓库。

## 授权

本项目使用 MIT License，详见 `LICENSE`。
