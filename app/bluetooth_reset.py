from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

APP_NAME = "Bluetooth Reset"
TARGET_NAME = "Intel(R) Wireless Bluetooth(R)"
ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "logs" / "bluetooth-reset.log"


@dataclass(frozen=True)
class AdapterState:
    name: str
    instance_id: str
    status: str

    @property
    def enabled(self) -> bool:
        return self.status.lower() == "ok"


def quote_ps(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    params = subprocess.list2cmdline(sys.argv)
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, str(ROOT), 1)
    if result <= 32:
        raise RuntimeError("Windows kon geen beheerdersrechten starten.")


def run_powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def discover_adapter(preferred_name: str = TARGET_NAME) -> AdapterState:
    script = f"""
$preferred = {quote_ps(preferred_name)}
$device = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
    Where-Object {{ $_.FriendlyName -eq $preferred }} | Select-Object -First 1
if (-not $device) {{
    $device = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
        Where-Object {{ $_.FriendlyName -match 'Bluetooth' -and $_.InstanceId -match 'USB|PCI' }} |
        Select-Object -First 1
}}
if (-not $device) {{ exit 3 }}
$device | Select-Object FriendlyName, InstanceId, Status | ConvertTo-Json -Compress
"""
    result = run_powershell(script)
    if result.returncode == 3 or not result.stdout.strip():
        raise RuntimeError("Geen Bluetooth-adapter gevonden.")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Adapterstatus kon niet worden gelezen.")
    data = json.loads(result.stdout.strip())
    return AdapterState(data.get("FriendlyName", "Bluetooth-adapter"), data["InstanceId"], data.get("Status", "Unknown"))


def set_adapter_enabled(instance_id: str, enabled: bool) -> None:
    cmdlet = "Enable-PnpDevice" if enabled else "Disable-PnpDevice"
    result = run_powershell(f"{cmdlet} -InstanceId {quote_ps(instance_id)} -Confirm:$false -ErrorAction Stop")
    if result.returncode != 0:
        action = "ingeschakeld" if enabled else "uitgeschakeld"
        raise RuntimeError(result.stderr.strip() or f"Adapter kon niet worden {action}.")


def log(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")


class BluetoothResetApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("500x430")
        self.resizable(False, False)
        self.configure(bg="#0b1220")
        self.adapter: AdapterState | None = None
        self.busy = False
        self._build_ui()
        self.after(150, self.refresh_status)

    def _build_ui(self) -> None:
        tk.Label(self, text="Bluetooth Reset", font=("Segoe UI Semibold", 24), fg="white", bg="#0b1220").pack(pady=(28, 6))
        tk.Label(self, text="Herstel je adapter zonder Apparaatbeheer", font=("Segoe UI", 10), fg="#94a3b8", bg="#0b1220").pack()

        card = tk.Frame(self, bg="#111c31", padx=24, pady=22)
        card.pack(fill="both", expand=True, padx=28, pady=24)

        self.status_label = tk.Label(card, text="Adapter controleren…", font=("Segoe UI Semibold", 16), fg="#e2e8f0", bg="#111c31")
        self.status_label.pack(pady=(2, 6))
        self.detail_label = tk.Label(card, text="", font=("Segoe UI", 9), fg="#94a3b8", bg="#111c31", wraplength=400)
        self.detail_label.pack(pady=(0, 20))

        self.reset_button = tk.Button(card, text="↻  Reset Bluetooth", command=self.reset_adapter, font=("Segoe UI Semibold", 13), fg="white", bg="#1677ff", activebackground="#0f63d9", activeforeground="white", relief="flat", cursor="hand2", pady=12)
        self.reset_button.pack(fill="x", pady=(0, 12))
        self.toggle_button = tk.Button(card, text="Bluetooth aan / uit", command=self.toggle_adapter, font=("Segoe UI", 11), fg="#dbeafe", bg="#1e293b", activebackground="#334155", activeforeground="white", relief="flat", cursor="hand2", pady=10)
        self.toggle_button.pack(fill="x")
        tk.Label(card, text="Draait alleen wanneer jij de tool opent.", font=("Segoe UI", 8), fg="#64748b", bg="#111c31").pack(pady=(20, 0))

    def set_busy(self, busy: bool, text: str | None = None) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.reset_button.configure(state=state)
        self.toggle_button.configure(state=state)
        if text:
            self.status_label.configure(text=text, fg="#fbbf24")

    def background(self, task) -> None:
        threading.Thread(target=task, daemon=True).start()

    def refresh_status(self) -> None:
        if self.busy:
            return
        def task() -> None:
            try:
                adapter = discover_adapter()
                self.adapter = adapter
                self.after(0, lambda: self.show_adapter(adapter))
            except Exception as exc:
                self.after(0, lambda: self.show_error(str(exc)))
        self.background(task)

    def show_adapter(self, adapter: AdapterState) -> None:
        state_text = "AAN" if adapter.enabled else "UIT"
        color = "#4ade80" if adapter.enabled else "#f87171"
        self.status_label.configure(text=f"Bluetooth is {state_text}", fg=color)
        self.detail_label.configure(text=f"{adapter.name}\nStatus: {adapter.status}")
        self.toggle_button.configure(text=f"Bluetooth {'uitschakelen' if adapter.enabled else 'inschakelen'}")
        self.set_busy(False)

    def show_error(self, message: str) -> None:
        self.status_label.configure(text="Bluetooth niet beschikbaar", fg="#f87171")
        self.detail_label.configure(text=message)
        self.set_busy(False)

    def reset_adapter(self) -> None:
        if self.busy:
            return
        self.set_busy(True, "Bluetooth resetten…")
        def task() -> None:
            try:
                adapter = discover_adapter()
                log(f"Reset gestart voor {adapter.name}")
                set_adapter_enabled(adapter.instance_id, False)
                time.sleep(2)
                set_adapter_enabled(adapter.instance_id, True)
                time.sleep(1)
                refreshed = discover_adapter()
                log(f"Reset voltooid. Status: {refreshed.status}")
                self.after(0, lambda: self.show_adapter(refreshed))
            except Exception as exc:
                log(f"Reset mislukt: {exc}")
                self.after(0, lambda: self.operation_failed(str(exc)))
        self.background(task)

    def toggle_adapter(self) -> None:
        if self.busy:
            return
        self.set_busy(True, "Bluetooth wijzigen…")
        def task() -> None:
            try:
                adapter = discover_adapter()
                target = not adapter.enabled
                set_adapter_enabled(adapter.instance_id, target)
                time.sleep(1)
                refreshed = discover_adapter()
                log(f"Adapter {'ingeschakeld' if target else 'uitgeschakeld'}: {adapter.name}")
                self.after(0, lambda: self.show_adapter(refreshed))
            except Exception as exc:
                log(f"Schakelen mislukt: {exc}")
                self.after(0, lambda: self.operation_failed(str(exc)))
        self.background(task)

    def operation_failed(self, message: str) -> None:
        self.show_error(message)
        messagebox.showerror(APP_NAME, message)


def main() -> None:
    if os.name != "nt":
        raise SystemExit("Bluetooth Reset werkt alleen op Windows.")
    if not is_admin():
        try:
            relaunch_as_admin()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
        return
    BluetoothResetApp().mainloop()


if __name__ == "__main__":
    main()
