from __future__ import annotations

import ctypes
import json
import os
import queue
import re
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

import httpx
import pystray
from PIL import Image
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, OpenAIError


APP_NAME = "cxp1_desktop_translator"
APP_VERSION = "2.3"
BASE_URL = "https://api.poe.com/v1"
DEFAULT_MODEL = "gpt-5.3-instant"
DEFAULT_PROXY = "socks5://127.0.0.1:10808"
DEFAULT_GEOMETRY = "980x720+120+120"
DEFAULT_FONT_SIZE = 11
MIN_FONT_SIZE = 9
MAX_FONT_SIZE = 22
TRANSLATION_LOG = Path(__file__).resolve().parent / "trans_log.txt"
TRAY_ICON_PATH = Path(__file__).resolve().parent / "icon.png"
APP_MARK = "K.Y."
ACTION_BUTTON_WIDTH = 8

COLOR_BG = "#202020"
COLOR_PANEL = "#242424"
COLOR_PANEL_ALT = "#2b2b2b"
COLOR_FIELD = "#1f1f1f"
COLOR_BORDER = "#3c3c3c"
COLOR_TEXT = "#f2f2f2"
COLOR_TEXT_MUTED = "#c8c8c8"
COLOR_ACCENT = "#5aa0e6"
COLOR_BUTTON = "#303030"
COLOR_BUTTON_ACTIVE = "#3a3a3a"
COLOR_SELECT_BG = "#345f8f"
COLOR_SELECT_FG = "#ffffff"

UI_FONT_FAMILY = "Segoe UI"
TEXT_FONT_FAMILY = "Microsoft YaHei UI"
MONO_FONT_FAMILY = "Consolas"

SYSTEM_PROMPT = (
    "你是一个中、英文翻译的专家。不是字面翻译，而是要充分理解词语、句子、段落的真实含义，"
    "提供最地道的英语或者中文翻译结果。当你收到中文内容，你就直接提供英文翻译内容。"
    "当你收到英文内容，就提供中文翻译内容。除了内容以外，一个字都不要多说。"
)


def get_config_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        config_dir = Path(appdata) / APP_NAME
    else:
        config_dir = Path.home() / f".{APP_NAME}"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def default_config() -> dict[str, object]:
    return {
        "api_key": "",
        "window_geometry": DEFAULT_GEOMETRY,
        "proxy_enabled": True,
        "proxy_url": DEFAULT_PROXY,
        "debug_enabled": True,
        "model": DEFAULT_MODEL,
        "font_size": DEFAULT_FONT_SIZE,
        "topmost": False,
    }


def load_config() -> dict[str, object]:
    config = default_config()
    config_path = get_config_path()
    try:
        if config_path.exists():
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass
    return config


def save_config(config: dict[str, object]) -> None:
    config_path = get_config_path()
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def contains_chinese(text: str) -> bool:
    return re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text) is not None


def mask_key(api_key: str) -> str:
    if not api_key:
        return "missing"
    if len(api_key) <= 4:
        return "****"
    return f"present ****{api_key[-4:]}"


class TranslatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.active_client: OpenAI | None = None
        self.active_http_client: httpx.Client | None = None
        self.tray_icon: pystray.Icon | None = None
        self.is_exiting = False

        self.api_key_var = tk.StringVar(value=str(self.config.get("api_key", "")))
        self.model_var = tk.StringVar(value=str(self.config.get("model", DEFAULT_MODEL)))
        self.proxy_enabled_var = tk.BooleanVar(value=bool(self.config.get("proxy_enabled", True)))
        self.proxy_url_var = tk.StringVar(value=str(self.config.get("proxy_url", DEFAULT_PROXY)))
        self.debug_enabled_var = tk.BooleanVar(value=bool(self.config.get("debug_enabled", True)))
        self.topmost_var = tk.BooleanVar(value=bool(self.config.get("topmost", False)))
        self.font_size = self._read_font_size()
        self.status_var = tk.StringVar(value="就绪")

        self._apply_font_size()
        self._setup_theme()
        self._build_ui()
        self._apply_window_settings()
        self._bind_events()
        self.root.after(250, self.setup_tray)

        self.log_debug("INFO config_loaded")
        self.log_debug(f"INFO api_key {mask_key(self.api_key_var.get().strip())}")
        if self.proxy_enabled_var.get():
            self.log_debug(f"INFO proxy_enabled {self.proxy_url_var.get().strip()}")
        self._poll_events()

    def _build_ui(self) -> None:
        self.root.title(f"英汉 / 汉英翻译器 v{APP_VERSION}")
        self.root.configure(bg=COLOR_BG)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        settings = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        settings.grid(row=0, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)
        settings.columnconfigure(4, minsize=110)
        settings.columnconfigure(5, minsize=96)

        ttk.Label(settings, text="POE API Key").grid(row=0, column=0, sticky="w", padx=(0, 8))
        api_entry = ttk.Entry(settings, textvariable=self.api_key_var, show="*", width=34)
        api_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        ttk.Label(settings, text="模型").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(settings, textvariable=self.model_var, width=24).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        ttk.Button(settings, text="应用", command=self.apply_settings).grid(row=0, column=4, columnspan=2, sticky="ew")

        proxy_check = ttk.Checkbutton(settings, text="使用代理", variable=self.proxy_enabled_var, command=self.apply_settings)
        proxy_check.grid(row=1, column=0, sticky="w", pady=(8, 0), padx=(0, 8))
        ttk.Entry(settings, textvariable=self.proxy_url_var).grid(row=1, column=1, columnspan=3, sticky="ew", pady=(8, 0), padx=(0, 10))
        ttk.Checkbutton(settings, text="置顶", variable=self.topmost_var, command=self.toggle_topmost).grid(row=1, column=4, sticky="w", pady=(8, 0), padx=(0, 8))
        ttk.Checkbutton(settings, text="Debug", variable=self.debug_enabled_var, command=self.toggle_debug).grid(row=1, column=5, sticky="e", pady=(8, 0))

        body = ttk.Frame(self.root, padding=(12, 6, 12, 6))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        input_header = ttk.Frame(body)
        output_header = ttk.Frame(body)
        input_header.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        output_header.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        input_header.columnconfigure(0, weight=1)
        output_header.columnconfigure(0, weight=1)
        ttk.Label(input_header, text="原文").grid(row=0, column=0, sticky="w")
        ttk.Button(input_header, text="清空", width=6, command=self.clear_input).grid(row=0, column=1, sticky="e")
        ttk.Label(output_header, text="译文").grid(row=0, column=0, sticky="w")
        ttk.Button(output_header, text="复制", width=6, command=self.copy_output).grid(row=0, column=1, sticky="e")

        input_frame = ttk.Frame(body)
        output_frame = ttk.Frame(body)
        input_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(4, 0))
        output_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(4, 0))
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.input_text = self._create_text_widget(input_frame, undo=True, height=18)
        self.output_text = self._create_text_widget(output_frame, height=18)
        input_scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=self.input_text.yview)
        output_scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        self.input_text.configure(yscrollcommand=input_scrollbar.set)
        self.output_text.configure(yscrollcommand=output_scrollbar.set)
        self.input_text.grid(row=0, column=0, sticky="nsew")
        input_scrollbar.grid(row=0, column=1, sticky="ns")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        output_scrollbar.grid(row=0, column=1, sticky="ns")

        controls = ttk.Frame(self.root, padding=(12, 4, 12, 6))
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(5, weight=1)

        self.translate_button = ttk.Button(controls, text="翻译", width=ACTION_BUTTON_WIDTH, command=self.start_translation)
        self.translate_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(controls, text="历史", width=ACTION_BUTTON_WIDTH, command=self.open_history).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(controls, text="字体-", width=ACTION_BUTTON_WIDTH, command=lambda: self.change_font_size(-1)).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(controls, text="字体+", width=ACTION_BUTTON_WIDTH, command=lambda: self.change_font_size(1)).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(controls, text="退出", width=ACTION_BUTTON_WIDTH, command=self.exit_app).grid(row=0, column=4, padx=(0, 8))
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=5, sticky="w")
        ttk.Label(controls, text=f"v{APP_VERSION}  {APP_MARK}", style="Brand.TLabel").grid(row=0, column=6, sticky="e")

        self.debug_frame = ttk.LabelFrame(self.root, text="Debug", padding=(12, 6, 12, 10))
        self.debug_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.debug_frame.columnconfigure(0, weight=1)
        self.debug_frame.rowconfigure(0, weight=1)
        self.debug_text = self._create_text_widget(self.debug_frame, height=8, state="disabled", mono=True)
        debug_scrollbar = ttk.Scrollbar(self.debug_frame, orient="vertical", command=self.debug_text.yview)
        self.debug_text.configure(yscrollcommand=debug_scrollbar.set)
        self.debug_text.grid(row=0, column=0, sticky="nsew")
        debug_scrollbar.grid(row=0, column=1, sticky="ns")

        if not self.debug_enabled_var.get():
            self.debug_frame.grid_remove()

    def _setup_theme(self) -> None:
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, fieldbackground=COLOR_FIELD)
        self.style.configure("TFrame", background=COLOR_BG)
        self.style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        self.style.configure("Brand.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_MUTED)
        self.style.configure("TLabelframe", background=COLOR_BG, bordercolor=COLOR_BORDER)
        self.style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_TEXT_MUTED)
        self.style.configure(
            "TButton",
            background=COLOR_BUTTON,
            foreground=COLOR_TEXT,
            bordercolor=COLOR_BORDER,
            focusthickness=1,
            focuscolor=COLOR_ACCENT,
            padding=(12, 5),
        )
        self.style.map(
            "TButton",
            background=[("active", COLOR_BUTTON_ACTIVE), ("pressed", COLOR_PANEL_ALT)],
            foreground=[("disabled", "#777777")],
        )
        self.style.configure(
            "TCheckbutton",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            focuscolor=COLOR_ACCENT,
        )
        self.style.map(
            "TCheckbutton",
            background=[("active", COLOR_BG)],
            foreground=[("disabled", "#777777")],
        )
        self.style.configure(
            "TEntry",
            fieldbackground=COLOR_FIELD,
            foreground=COLOR_TEXT,
            insertcolor=COLOR_TEXT,
            bordercolor=COLOR_BORDER,
            lightcolor=COLOR_BORDER,
            darkcolor=COLOR_BORDER,
        )
        self.style.map(
            "TEntry",
            fieldbackground=[("focus", COLOR_FIELD)],
            bordercolor=[("focus", COLOR_ACCENT)],
        )
        self.style.configure(
            "Vertical.TScrollbar",
            background=COLOR_PANEL_ALT,
            troughcolor=COLOR_FIELD,
            bordercolor=COLOR_BORDER,
            arrowcolor=COLOR_TEXT_MUTED,
            gripcount=0,
        )
        self.style.map("Vertical.TScrollbar", background=[("active", COLOR_BUTTON_ACTIVE)])

    def _create_text_widget(
        self,
        parent: tk.Widget,
        *,
        undo: bool = False,
        height: int = 8,
        state: str = "normal",
        mono: bool = False,
    ) -> tk.Text:
        font_name = "TkFixedFont" if mono else "TkTextFont"
        return tk.Text(
            parent,
            wrap="word",
            undo=undo,
            height=height,
            state=state,
            font=font_name,
            bg=COLOR_FIELD,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            selectbackground=COLOR_SELECT_BG,
            selectforeground=COLOR_SELECT_FG,
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_ACCENT,
            padx=8,
            pady=6,
        )

    def _apply_window_settings(self) -> None:
        geometry = str(self.config.get("window_geometry", DEFAULT_GEOMETRY))
        self.root.geometry(geometry)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", self.topmost_var.get())

    def _bind_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.input_text.bind("<Control-Return>", lambda _event: self.start_translation())

    def log_startup_debug(self, message: str) -> None:
        if hasattr(self, "debug_text"):
            self.log_debug(message)

    def setup_tray(self) -> None:
        try:
            image = self.load_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem("显示/隐藏", self.on_tray_toggle, default=True),
                pystray.MenuItem("退出", self.on_tray_exit),
            )
            self.tray_icon = pystray.Icon(APP_NAME, image, f"英汉 / 汉英翻译器 v{APP_VERSION}", menu)
            self.tray_icon.run_detached()
            self.hide_from_taskbar()
            self.log_debug("INFO tray_started")
        except Exception as exc:
            self.log_debug(f"ERROR tray_failed {self.short_error(exc)}")

    def load_tray_image(self) -> Image.Image:
        if TRAY_ICON_PATH.exists():
            image = Image.open(TRAY_ICON_PATH).convert("RGBA")
        else:
            image = Image.new("RGBA", (64, 64), COLOR_ACCENT)
        return image.resize((64, 64), Image.Resampling.LANCZOS)

    def hide_from_taskbar(self) -> None:
        if sys.platform != "win32":
            return
        try:
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            self.delete_taskbar_tab(hwnd)
        except Exception as exc:
            self.log_debug(f"ERROR taskbar_hide_failed {self.short_error(exc)}")

    def delete_taskbar_tab(self, hwnd: int) -> None:
        clsid_taskbar_list = self.GUID("{56FDF344-FD6D-11d0-958A-006097C9A090}")
        iid_itaskbar_list = self.GUID("{56FDF342-FD6D-11d0-958A-006097C9A090}")
        taskbar = ctypes.c_void_p()
        ctypes.windll.ole32.CoInitialize(None)
        result = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(clsid_taskbar_list),
            None,
            1,
            ctypes.byref(iid_itaskbar_list),
            ctypes.byref(taskbar),
        )
        if result != 0 or not taskbar.value:
            raise OSError(f"CoCreateInstance(ITaskbarList) failed: 0x{result & 0xFFFFFFFF:08X}")

        vtable = ctypes.cast(taskbar, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        hr_init = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])
        delete_tab = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(vtable[5])
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        try:
            result = hr_init(taskbar)
            if result != 0:
                raise OSError(f"ITaskbarList.HrInit failed: 0x{result & 0xFFFFFFFF:08X}")
            result = delete_tab(taskbar, ctypes.c_void_p(hwnd))
            if result != 0:
                raise OSError(f"ITaskbarList.DeleteTab failed: 0x{result & 0xFFFFFFFF:08X}")
        finally:
            release(taskbar)

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

        def __init__(self, guid_string: str) -> None:
            import uuid

            guid = uuid.UUID(guid_string)
            fields = guid.fields
            data4 = (ctypes.c_ubyte * 8)(fields[3], fields[4], *guid.node.to_bytes(6, "big"))
            super().__init__(fields[0], fields[1], fields[2], data4)

    def on_tray_toggle(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.toggle_window_visibility)

    def on_tray_exit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.exit_app)

    def toggle_window_visibility(self) -> None:
        if self.root.state() == "withdrawn":
            self.show_window()
        else:
            self.hide_window()

    def show_window(self) -> None:
        self.root.state("normal")
        self.root.deiconify()
        self.root.update_idletasks()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", self.topmost_var.get())
        self.root.after(80, self.hide_from_taskbar)
        self.log_debug("INFO window_shown")

    def hide_window(self) -> None:
        self.save_current_config()
        self.root.withdraw()
        self.log_debug("INFO window_hidden_to_tray")

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "success":
                    self.on_translation_success(str(payload))
                elif event == "error":
                    self.on_translation_error(str(payload))
                elif event == "debug":
                    self.log_debug(str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def apply_settings(self) -> None:
        self.config.update(
            {
                "api_key": self.api_key_var.get().strip(),
                "model": self.model_var.get().strip() or DEFAULT_MODEL,
                "proxy_enabled": self.proxy_enabled_var.get(),
                "proxy_url": self.proxy_url_var.get().strip() or DEFAULT_PROXY,
                "debug_enabled": self.debug_enabled_var.get(),
                "window_geometry": self.root.geometry(),
                "font_size": self.font_size,
                "topmost": self.topmost_var.get(),
            }
        )
        self.model_var.set(str(self.config["model"]))
        self.proxy_url_var.set(str(self.config["proxy_url"]))
        save_config(self.config)
        self.status_var.set("设置已保存")
        self.log_debug(f"INFO settings_saved api_key={mask_key(str(self.config['api_key']))}")
        if self.proxy_enabled_var.get():
            self.log_debug(f"INFO proxy_enabled {self.proxy_url_var.get().strip()}")
        else:
            self.log_debug("INFO proxy_disabled")

    def toggle_topmost(self) -> None:
        self.root.attributes("-topmost", self.topmost_var.get())
        self.apply_settings()
        state = "enabled" if self.topmost_var.get() else "disabled"
        self.log_debug(f"INFO topmost_{state}")

    def change_font_size(self, delta: int) -> None:
        new_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, self.font_size + delta))
        if new_size == self.font_size:
            self.log_debug(f"INFO font_size_limit size={self.font_size}")
            return
        self.font_size = new_size
        self._apply_font_size()
        self.apply_settings()
        self.log_debug(f"INFO font_size_changed size={self.font_size}")

    def _read_font_size(self) -> int:
        try:
            return int(self.config.get("font_size", DEFAULT_FONT_SIZE))
        except (TypeError, ValueError):
            return DEFAULT_FONT_SIZE

    def _apply_font_size(self) -> None:
        self.font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, self.font_size))
        for font_name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkFixedFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                named_font = tkfont.nametofont(font_name)
                if font_name == "TkFixedFont":
                    named_font.configure(family=MONO_FONT_FAMILY, size=self.font_size)
                elif font_name == "TkTextFont":
                    named_font.configure(family=TEXT_FONT_FAMILY, size=self.font_size)
                else:
                    named_font.configure(family=UI_FONT_FAMILY, size=self.font_size)
            except tk.TclError:
                pass

    def toggle_debug(self) -> None:
        if self.debug_enabled_var.get():
            self.debug_frame.grid()
        else:
            self.debug_frame.grid_remove()
        self.apply_settings()

    def clear_input(self) -> None:
        self.input_text.delete("1.0", "end")
        self.status_var.set("原文已清空")
        self.log_debug("INFO input_cleared")

    def copy_output(self) -> None:
        translated = self.output_text.get("1.0", "end").strip()
        if not translated:
            self.status_var.set("没有可复制的译文")
            self.log_debug("ERROR copy_empty_output")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(translated)
        self.root.update()
        self.status_var.set("译文已复制")
        self.log_debug(f"INFO output_copied chars={len(translated)}")

    def start_translation(self) -> None:
        source_text = self.input_text.get("1.0", "end").strip()
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip() or DEFAULT_MODEL
        proxy_enabled = self.proxy_enabled_var.get()
        proxy_url = self.proxy_url_var.get().strip() or DEFAULT_PROXY

        if not source_text:
            self.status_var.set("请输入要翻译的内容")
            self.log_debug("ERROR empty_input")
            return
        if not api_key:
            self.status_var.set("请先填写 API Key 并点击应用")
            self.log_debug("ERROR missing_api_key")
            return

        self.apply_settings()
        direction = "zh_to_en" if contains_chinese(source_text) else "en_to_zh"
        self.translate_button.config(state="disabled")
        self.status_var.set("请求中...")
        self.log_debug(f"INFO request_start model={model} direction={direction} chars={len(source_text)}")

        thread = threading.Thread(
            target=self.translate_worker,
            args=(api_key, model, source_text, proxy_enabled, proxy_url),
            daemon=True,
        )
        thread.start()

    def translate_worker(
        self,
        api_key: str,
        model: str,
        source_text: str,
        proxy_enabled: bool,
        proxy_url: str,
    ) -> None:
        try:
            client = self.make_client(api_key, proxy_enabled, proxy_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": source_text},
                ],
                temperature=0,
            )
            translated = response.choices[0].message.content or ""
            translated = translated.strip()
            self.save_history(model, source_text, translated)
            self.events.put(("debug", f"INFO request_success output_chars={len(translated)}"))
            self.events.put(("debug", "INFO history_saved trans_log.txt"))
            self.events.put(("success", translated))
        except AuthenticationError:
            self.events.put(("error", "ERROR auth_failed check_api_key"))
        except APITimeoutError:
            self.events.put(("error", "ERROR timeout proxy_or_network"))
        except APIConnectionError as exc:
            self.events.put(("error", f"ERROR connection_failed proxy_or_network {self.short_error(exc)}"))
        except APIStatusError as exc:
            self.events.put(("error", f"ERROR api_error status={exc.status_code} message={self.short_error(exc)}"))
        except ImportError as exc:
            self.events.put(("error", f"ERROR socks_dependency_missing {self.short_error(exc)}"))
        except OpenAIError as exc:
            self.events.put(("error", f"ERROR openai_error {self.short_error(exc)}"))
        except Exception as exc:
            self.events.put(("error", f"ERROR unexpected {type(exc).__name__}: {self.short_error(exc)}"))

    def make_client(self, api_key: str, proxy_enabled: bool, proxy_url: str) -> OpenAI:
        self.close_http_client()
        if proxy_enabled:
            self.active_http_client = httpx.Client(proxy=proxy_url, timeout=60.0)
            return OpenAI(api_key=api_key, base_url=BASE_URL, http_client=self.active_http_client)
        return OpenAI(api_key=api_key, base_url=BASE_URL, timeout=60.0)

    def close_http_client(self) -> None:
        if self.active_http_client is not None:
            try:
                self.active_http_client.close()
            except Exception:
                pass
            self.active_http_client = None

    def on_translation_success(self, translated: str) -> None:
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", translated)
        self.status_var.set("翻译完成")
        self.translate_button.config(state="normal")

    def on_translation_error(self, error_message: str) -> None:
        self.status_var.set("翻译失败，查看 Debug")
        self.log_debug(error_message)
        self.translate_button.config(state="normal")

    def save_history(self, model: str, source_text: str, translated: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"[{timestamp}] model={model}\n"
            "[原文]\n"
            f"{source_text}\n\n"
            "[译文]\n"
            f"{translated}\n"
            f"{'-' * 72}\n\n"
        )
        TRANSLATION_LOG.write_text("", encoding="utf-8") if not TRANSLATION_LOG.exists() else None
        with TRANSLATION_LOG.open("a", encoding="utf-8") as log_file:
            log_file.write(entry)

    def open_history(self) -> None:
        if not TRANSLATION_LOG.exists():
            TRANSLATION_LOG.write_text("", encoding="utf-8")
        try:
            os.startfile(TRANSLATION_LOG)  # type: ignore[attr-defined]
            self.log_debug("INFO history_opened trans_log.txt")
        except OSError as exc:
            self.log_debug(f"ERROR history_open_failed {self.short_error(exc)}")
            messagebox.showerror("打开历史失败", str(exc))

    def log_debug(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"{timestamp} {message}\n"
        self.debug_text.config(state="normal")
        self.debug_text.insert("end", line)
        self.debug_text.see("end")
        self.debug_text.config(state="disabled")

    @staticmethod
    def short_error(exc: BaseException) -> str:
        text = str(exc).replace("\n", " ").strip()
        return text[:240] if text else type(exc).__name__

    def save_current_config(self) -> None:
        self.config.update(
            {
                "api_key": self.api_key_var.get().strip(),
                "model": self.model_var.get().strip() or DEFAULT_MODEL,
                "proxy_enabled": self.proxy_enabled_var.get(),
                "proxy_url": self.proxy_url_var.get().strip() or DEFAULT_PROXY,
                "debug_enabled": self.debug_enabled_var.get(),
                "window_geometry": self.root.geometry(),
                "font_size": self.font_size,
                "topmost": self.topmost_var.get(),
            }
        )
        save_config(self.config)

    def exit_app(self) -> None:
        self.is_exiting = True
        self.save_current_config()
        self.close_http_client()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    TranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
