# 英汉 / 汉英桌面翻译器

一个轻量的 Python Tkinter 桌面翻译小工具。输入英文输出中文，输入中文输出英文。默认使用 POE 的 OpenAI-compatible Chat Completions API 和 `gpt-5.3-instant`。

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

## 代理

界面默认启用 SOCKS 代理：

```text
socks5://127.0.0.1:10808
```

如果你使用 V2RAYN 或其他本机代理，可以在界面中修改代理地址，或取消勾选“使用代理”直接连接。

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

每次成功翻译都会追加写入项目目录下的 `trans_log.txt`，包含时间戳、模型名、原文、译文。界面里的“打开历史”按钮会用系统默认文本编辑器打开该文件。

`trans_log.txt` 已经加入 `.gitignore`，避免把个人翻译内容提交到公开仓库。
