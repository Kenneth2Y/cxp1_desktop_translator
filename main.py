from __future__ import annotations

import json
import os
import queue
import re
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, OpenAIError


APP_NAME = "cxp1_desktop_translator"
BASE_URL = "https://api.poe.com/v1"
DEFAULT_MODEL = "gpt-5.3-instant"
DEFAULT_PROXY = "socks5://127.0.0.1:10808"
DEFAULT_GEOMETRY = "980x720+120+120"
TRANSLATION_LOG = Path(__file__).resolve().parent / "trans_log.txt"

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
    }


def load_config() -> dict[str, object]:
    config = default_config()
    config_path = get_config_path()
    if config_path.exists():
        try:
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

        self.api_key_var = tk.StringVar(value=str(self.config.get("api_key", "")))
        self.model_var = tk.StringVar(value=str(self.config.get("model", DEFAULT_MODEL)))
        self.proxy_enabled_var = tk.BooleanVar(value=bool(self.config.get("proxy_enabled", True)))
        self.proxy_url_var = tk.StringVar(value=str(self.config.get("proxy_url", DEFAULT_PROXY)))
        self.debug_enabled_var = tk.BooleanVar(value=bool(self.config.get("debug_enabled", True)))
        self.status_var = tk.StringVar(value="就绪")

        self._build_ui()
        self._apply_window_settings()
        self._bind_events()

        self.log_debug("INFO config_loaded")
        self.log_debug(f"INFO api_key {mask_key(self.api_key_var.get().strip())}")
        if self.proxy_enabled_var.get():
            self.log_debug(f"INFO proxy_enabled {self.proxy_url_var.get().strip()}")
        self._poll_events()

    def _build_ui(self) -> None:
        self.root.title("英汉 / 汉英翻译器")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        settings = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        settings.grid(row=0, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text="POE API Key").grid(row=0, column=0, sticky="w", padx=(0, 8))
        api_entry = ttk.Entry(settings, textvariable=self.api_key_var, show="*", width=34)
        api_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        ttk.Label(settings, text="模型").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(settings, textvariable=self.model_var, width=24).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        ttk.Button(settings, text="应用", command=self.apply_settings).grid(row=0, column=4, sticky="e")

        proxy_check = ttk.Checkbutton(settings, text="使用代理", variable=self.proxy_enabled_var, command=self.apply_settings)
        proxy_check.grid(row=1, column=0, sticky="w", pady=(8, 0), padx=(0, 8))
        ttk.Entry(settings, textvariable=self.proxy_url_var).grid(row=1, column=1, columnspan=3, sticky="ew", pady=(8, 0), padx=(0, 10))
        ttk.Checkbutton(settings, text="Debug", variable=self.debug_enabled_var, command=self.toggle_debug).grid(row=1, column=4, sticky="e", pady=(8, 0))

        body = ttk.Frame(self.root, padding=(12, 6, 12, 6))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="原文").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="译文").grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.input_text = tk.Text(body, wrap="word", undo=True, height=18)
        self.output_text = tk.Text(body, wrap="word", height=18)
        self.input_text.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(4, 0))
        self.output_text.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(4, 0))

        controls = ttk.Frame(self.root, padding=(12, 4, 12, 6))
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(2, weight=1)

        self.translate_button = ttk.Button(controls, text="翻译", command=self.start_translation)
        self.translate_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(controls, text="打开历史", command=self.open_history).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(controls, text="退出", command=self.on_close).grid(row=0, column=2, padx=(0, 8))
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=3, sticky="w")

        self.debug_frame = ttk.LabelFrame(self.root, text="Debug", padding=(12, 6, 12, 10))
        self.debug_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.debug_frame.columnconfigure(0, weight=1)
        self.debug_frame.rowconfigure(0, weight=1)
        self.debug_text = tk.Text(self.debug_frame, wrap="word", height=8, state="disabled")
        self.debug_text.grid(row=0, column=0, sticky="nsew")

        if not self.debug_enabled_var.get():
            self.debug_frame.grid_remove()

    def _apply_window_settings(self) -> None:
        geometry = str(self.config.get("window_geometry", DEFAULT_GEOMETRY))
        self.root.geometry(geometry)
        self.root.resizable(False, False)

    def _bind_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.input_text.bind("<Control-Return>", lambda _event: self.start_translation())

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

    def toggle_debug(self) -> None:
        if self.debug_enabled_var.get():
            self.debug_frame.grid()
        else:
            self.debug_frame.grid_remove()
        self.apply_settings()

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

    def on_close(self) -> None:
        self.config.update(
            {
                "api_key": self.api_key_var.get().strip(),
                "model": self.model_var.get().strip() or DEFAULT_MODEL,
                "proxy_enabled": self.proxy_enabled_var.get(),
                "proxy_url": self.proxy_url_var.get().strip() or DEFAULT_PROXY,
                "debug_enabled": self.debug_enabled_var.get(),
                "window_geometry": self.root.geometry(),
            }
        )
        save_config(self.config)
        self.close_http_client()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    TranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
