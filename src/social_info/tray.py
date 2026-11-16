import asyncio
import ctypes
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import httpx
import pystray
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .icon import social_icon

URL = "http://127.0.0.1:8765/mcp"


class TrayApp:
    def __init__(self):
        self.base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SocialInfo"
        self.base.mkdir(parents=True, exist_ok=True)
        self.process = None
        self.log_file = None
        self.status_pending = False
        self.root = tk.Tk()
        self.root.title("Social Info")
        self.root.geometry("360x275")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.status = tk.StringVar(value="正在启动本地服务…")
        tk.Label(self.root, text="Social Info", font=("Microsoft YaHei", 18, "bold")).pack(pady=(18, 4))
        tk.Label(self.root, textvariable=self.status, wraplength=320).pack(pady=8)
        frame = tk.Frame(self.root)
        frame.pack(pady=8)
        for index, (text, command) in enumerate((
            ("登录小红书", self.login), ("登录完成", self.login_done),
            ("检查状态", self.refresh), ("启动服务", self.start),
            ("停止服务", self.stop), ("打开日志", self.open_logs),
        )):
            tk.Button(frame, text=text, width=12,
                      command=lambda cmd=command: self.worker(cmd)).grid(
                          row=index // 2, column=index % 2, padx=4, pady=4)
        tk.Button(self.root, text="使用说明", width=12,
                  command=lambda: webbrowser.open("https://github.com/949025590/Social-info#readme")).pack()
        tk.Label(self.root, text="关闭窗口只会隐藏到托盘；退出请在托盘图标右键操作。",
                 fg="#666").pack(pady=8)
        self.icon = pystray.Icon("SocialInfo", social_icon(), "Social Info", pystray.Menu(
            pystray.MenuItem("打开控制面板", self.show, default=True),
            pystray.MenuItem("登录小红书", lambda: self.worker(self.login)),
            pystray.MenuItem("打开日志目录", self.open_logs),
            pystray.MenuItem("退出", lambda: self.worker(self.exit)),
        ))

    def set_status(self, text):
        self.root.after(0, self.status.set, text)

    def worker(self, func, quiet=False):
        def run():
            try:
                func()
            except Exception as exc:
                self.set_status(f"操作失败：{exc}")
                if not quiet:
                    self.root.after(0, lambda: messagebox.showerror("Social Info", str(exc)))
        threading.Thread(target=run, daemon=True).start()

    async def _call_async(self, name, args=None):
        async with httpx.AsyncClient(timeout=10) as http:
            async with streamable_http_client(URL, http_client=http) as (read, write, _):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    result = await client.call_tool(name, args or {})
        data = result.structuredContent
        if not data or not data.get("ok"):
            raise RuntimeError((data or {}).get("error", {"message": "服务未返回有效结果"})["message"])
        return data

    def call(self, name, args=None):
        return asyncio.run(self._call_async(name, args))

    def start(self):
        if self.process and self.process.poll() is None:
            self.set_status("服务正在运行")
            return
        self.base.mkdir(parents=True, exist_ok=True)
        self.log_file = (self.base / "service.log").open("a", encoding="utf-8")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "serve", "--transport", "http"]
        else:
            command = [sys.executable, "-m", "social_info", "serve", "--transport", "http"]
        self.process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=self.log_file, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        for _ in range(40):
            try:
                self.call("social_session_status")
                self.set_status("服务已启动；Agent 可连接本机 MCP")
                return
            except Exception:
                if self.process.poll() is not None:
                    raise RuntimeError("服务启动失败，请查看 service.log")
                threading.Event().wait(0.25)
        raise RuntimeError("服务启动超时，请查看 service.log")

    def login(self):
        self.start()
        self.call("social_login_start")
        self.set_status("请在浏览器中扫码；完成后点击本窗口的“登录完成”")

    def login_done(self):
        self.call("social_login_finish")
        self.set_status("登录状态已保存，已切换到后台模式")

    def refresh(self):
        self.start()
        state = self.call("social_session_status")
        auth = {"logged_in": "已登录", "logged_out": "未登录"}.get(state["auth"], state["auth"])
        self.set_status(f"服务正常；浏览器：{state['browser']}；账号：{auth}")

    def stop(self):
        if not self.process:
            self.set_status("服务已停止")
            return
        try:
            self.call("social_server_stop")
            self.process.wait(timeout=8)
        except Exception:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
        finally:
            self.process = None
            if self.log_file:
                self.log_file.close()
                self.log_file = None
        self.set_status("服务已停止")

    def hide(self):
        self.root.withdraw()

    def show(self):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def open_logs(self):
        os.startfile(self.base)

    def exit(self):
        self.stop()
        self.root.after(0, self.root.destroy)

    def periodic_status(self):
        if self.process and self.process.poll() is None and not self.status_pending:
            self.status_pending = True
            def check():
                try:
                    self.refresh()
                finally:
                    self.status_pending = False
            self.worker(check, quiet=True)
        self.root.after(10000, self.periodic_status)

    def run(self):
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.worker(self.start)
        self.root.after(10000, self.periodic_status)
        self.root.mainloop()
        self.icon.stop()


def main():
    ctypes.windll.kernel32.SetLastError(0)
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\SocialInfoTray")
    if ctypes.windll.kernel32.GetLastError() == 183:
        messagebox.showinfo("Social Info", "程序已经在后台运行，请查看系统托盘。")
        return
    TrayApp().run()
