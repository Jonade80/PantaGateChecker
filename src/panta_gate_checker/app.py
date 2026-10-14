from __future__ import annotations

import queue
import re
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from .grpc_client import PandoraGrpcClient
from .report import create_pdf_report
from .runner import CycleResult, GateTestRunner, TestSummary

DEFAULT_TEST_NAME = "Gate Test"
DEFAULT_OUTPUT_DIRECTORY = Path.home() / "Documents"
DEFAULT_PANDORA_ENDPOINT = "172.16.4.1:2316"


class GateCheckerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Panta Gate Checker")
        self.geometry("940x766")
        self.minsize(780, 666)
        self.configure(bg="#F3F1EA")
        icon_path = _resource_path("PantaGateChecker.ico")
        if icon_path.exists():
            self.iconbitmap(default=str(icon_path))

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None

        self.endpoint = tk.StringVar(value=DEFAULT_PANDORA_ENDPOINT)
        self.test_name = tk.StringVar(value=DEFAULT_TEST_NAME)
        self.cycles = tk.StringVar(value="10")
        self.cancel_percent = tk.StringVar(value="10")
        self.output_directory = tk.StringVar(value=str(DEFAULT_OUTPUT_DIRECTORY))
        self.device_name = tk.StringVar(value="Not connected")
        self.status = tk.StringVar(value="Ready")
        self.test_time = tk.StringVar()
        self.test_started_at: float | None = None
        self.timer_job: str | None = None
        self._update_time_estimate()

        self._configure_styles()
        self._build_ui()
        self.after(100, self._process_events)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#F3F1EA")
        style.configure("Panel.TFrame", background="#FFFFFF")
        style.configure("TLabel", background="#F3F1EA", foreground="#25332E", font=("Aptos", 10))
        style.configure("Panel.TLabel", background="#FFFFFF", foreground="#25332E", font=("Aptos", 10))
        style.configure("Title.TLabel", background="#153F35", foreground="#FFFFFF", font=("Aptos Display", 22, "bold"))
        style.configure("Subtitle.TLabel", background="#153F35", foreground="#D7E7DE", font=("Aptos", 10))
        style.configure("Accent.TButton", background="#D97A32", foreground="#FFFFFF", font=("Aptos", 10, "bold"), padding=(16, 9))
        style.map("Accent.TButton", background=[("active", "#B95F21"), ("disabled", "#C9C5BE")])
        style.configure("TButton", font=("Aptos", 10), padding=(12, 8))
        style.configure("Treeview", font=("Aptos", 9), rowheight=28, background="#FFFFFF", fieldbackground="#FFFFFF")
        style.configure("Treeview.Heading", font=("Aptos", 9, "bold"), background="#E5ECE8", foreground="#153F35")

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg="#153F35", height=150)
        header.pack(fill="x")
        header.pack_propagate(False)

        product_image_path = _resource_path("prometheus-panta.webp")
        if product_image_path.exists():
            with Image.open(product_image_path) as product_image:
                fitted_image = ImageOps.fit(
                    product_image.convert("RGB"),
                    (300, 150),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.45, 0.5),
                )
            self.product_photo = ImageTk.PhotoImage(fitted_image)
            tk.Label(header, image=self.product_photo, bg="#153F35", borderwidth=0).pack(side="right")

        title_area = tk.Frame(header, bg="#153F35")
        title_area.pack(side="left", fill="both", expand=True)
        ttk.Label(title_area, text="Panta Gate Checker", style="Title.TLabel").pack(anchor="w", padx=28, pady=(40, 0))
        ttk.Label(title_area, text="Controlled endurance testing through Pandora gRPC", style="Subtitle.TLabel").pack(anchor="w", padx=30, pady=(2, 0))

        content = ttk.Frame(self, padding=22)
        content.pack(fill="both", expand=True)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(1, weight=1)

        settings = ttk.Frame(content, style="Panel.TFrame", padding=18)
        settings.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        device_row = ttk.Frame(settings, style="Panel.TFrame")
        device_row.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 12))
        device_row.columnconfigure(1, weight=1)
        ttk.Label(device_row, text="Device name / serial", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            device_row,
            textvariable=self.device_name,
            style="Panel.TLabel",
            font=("Aptos", 12, "bold"),
            foreground="#153F35",
        ).grid(row=0, column=1, sticky="w", padx=16)
        self.connect_button = ttk.Button(device_row, text="Check device", command=self._check_device)
        self.connect_button.grid(row=0, column=2, sticky="e")

        self._field(settings, "Pandora endpoint", self.endpoint, 1, 0)
        self._field(settings, "Test name", self.test_name, 1, 2)
        self._field(settings, "Number of cycles", self.cycles, 2, 0)
        self._field(settings, "Cancel open operations (%)", self.cancel_percent, 2, 2)

        ttk.Label(settings, text="Report folder", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(settings, textvariable=self.output_directory).grid(row=3, column=1, columnspan=2, sticky="ew", padx=(10, 8), pady=(12, 0))
        ttk.Button(settings, text="Browse...", command=self._choose_output_directory).grid(row=3, column=3, sticky="e", pady=(12, 0))

        results_frame = ttk.Frame(content, style="Panel.TFrame", padding=14)
        results_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        top_line = ttk.Frame(results_frame, style="Panel.TFrame")
        top_line.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(top_line, text="Cycle results", style="Panel.TLabel", font=("Aptos", 12, "bold")).pack(side="left")

        columns = ("cycle", "operation", "result", "details")
        self.results = ttk.Treeview(results_frame, columns=columns, show="headings")
        self.results.heading("cycle", text="Cycle")
        self.results.heading("operation", text="Operation")
        self.results.heading("result", text="Result")
        self.results.heading("details", text="Details")
        self.results.column("cycle", width=60, stretch=False, anchor="center")
        self.results.column("operation", width=140, stretch=False)
        self.results.column("result", width=80, stretch=False, anchor="center")
        self.results.column("details", width=440)
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results.yview)
        self.results.configure(yscrollcommand=scrollbar.set)
        self.results.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        footer = ttk.Frame(content)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        ttk.Label(footer, textvariable=self.status).pack(side="left")
        ttk.Label(footer, textvariable=self.test_time, foreground="#65736D").pack(side="left", padx=22)
        self.stop_button = ttk.Button(footer, text="Stop", command=self._stop, state="disabled")
        self.stop_button.pack(side="right", padx=(8, 0))
        self.start_button = ttk.Button(footer, text="Start test", style="Accent.TButton", command=self._start)
        self.start_button.pack(side="right")

    def _field(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int, column: int) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=column, sticky="w", pady=(0 if row == 0 else 12, 0))
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=column + 1, sticky="ew", padx=(10, 22), pady=(0 if row == 0 else 12, 0))

    def _choose_output_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_directory.get())
        if selected:
            self.output_directory.set(selected)

    def _update_time_estimate(self, *_args: object) -> None:
        if self.test_started_at is not None:
            return
        self.test_time.set("Duration depends on gate movement | state polled every 1 s")

    def _check_device(self) -> None:
        endpoint = self.endpoint.get().strip()
        if not endpoint:
            messagebox.showerror("Invalid settings", "Pandora endpoint is required", parent=self)
            return

        self.device_name.set("Connecting...")
        self.status.set("Reading device name / serial from Pandora...")
        self.connect_button.configure(state="disabled")
        self.worker = threading.Thread(target=self._read_device_name, args=(endpoint,), daemon=True)
        self.worker.start()

    def _read_device_name(self, endpoint: str) -> None:
        client = PandoraGrpcClient(endpoint)
        try:
            self.events.put(("device_checked", client.connect()))
        except Exception as error:
            self.events.put(("device_error", str(error)))
        finally:
            client.close()

    def _start(self) -> None:
        try:
            cycles = int(self.cycles.get())
            cancel_probability = float(self.cancel_percent.get()) / 100
            if cycles < 1:
                raise ValueError("Number of cycles must be at least 1")
            if not 0 <= cancel_probability <= 1:
                raise ValueError("Cancellation percentage must be from 0 to 100")
            if not self.endpoint.get().strip() or not self.test_name.get().strip():
                raise ValueError("Endpoint and test name are required")
        except ValueError as error:
            messagebox.showerror("Invalid settings", str(error), parent=self)
            return

        for item in self.results.get_children():
            self.results.delete(item)
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set("Connecting to Pandora...")
        self.test_started_at = time.monotonic()
        self._tick_timer()
        endpoint = self.endpoint.get().strip()
        test_name = self.test_name.get().strip()
        output_directory = self.output_directory.get()
        self.worker = threading.Thread(
            target=self._run_test,
            args=(cycles, cancel_probability, endpoint, test_name, output_directory),
            daemon=True,
        )
        self.worker.start()

    def _run_test(
        self,
        cycles: int,
        cancel_probability: float,
        endpoint: str,
        test_name: str,
        output_directory: str,
    ) -> None:
        client = PandoraGrpcClient(endpoint)
        started_at = datetime.now()
        try:
            device_name = client.connect()
            self.events.put(("connected", device_name))
            runner = GateTestRunner(client, cancellation_probability=cancel_probability)
            summary = runner.run(
                device_name=device_name,
                test_name=test_name,
                cycles=cycles,
                on_result=lambda result: self.events.put(("result", result)),
                stop_event=self.stop_event,
            )
        except Exception as error:
            summary = TestSummary(
                device_name="Unknown device",
                test_name=test_name,
                requested_cycles=cycles,
                results=(),
                started_at=started_at,
                finished_at=datetime.now(),
                error_message=str(error),
            )
            self.events.put(("error", str(error)))
        finally:
            client.close()

        report_name = _safe_filename(
            f"{summary.device_name}_{summary.test_name}_{summary.started_at:%Y%m%d_%H%M%S}.pdf"
        )
        try:
            report_path = create_pdf_report(summary, Path(output_directory) / report_name)
            self.events.put(("complete", (summary, report_path)))
        except Exception as error:
            self.events.put(("error", f"Could not create PDF report: {error}"))
            self.events.put(("finished", summary))

    def _stop(self) -> None:
        self.stop_event.set()
        self.status.set("Stopping after returning the gate to a safe state...")
        self.stop_button.configure(state="disabled")

    def _tick_timer(self) -> None:
        if self.test_started_at is None:
            return
        elapsed = int(time.monotonic() - self.test_started_at)
        self.test_time.set(f"Elapsed {_format_duration(elapsed)} | state polled every 1 s")
        self.timer_job = self.after(1000, self._tick_timer)

    def _process_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "connected":
                    self.device_name.set(str(payload))
                    self.status.set("Test running")
                elif event == "device_checked":
                    self.device_name.set(str(payload))
                    self.status.set("Device connected")
                    self.connect_button.configure(state="normal")
                elif event == "device_error":
                    self.device_name.set("Connection failed")
                    self.status.set(str(payload))
                    self.connect_button.configure(state="normal")
                elif event == "result":
                    result = payload
                    if isinstance(result, CycleResult):
                        self.results.insert(
                            "",
                            "end",
                            values=(
                                result.number,
                                "Open cancelled" if result.cancelled else "Open / close",
                                "PASS" if result.passed else "FAIL",
                                result.message,
                            ),
                        )
                elif event == "error":
                    self.status.set(str(payload))
                elif event == "complete":
                    summary, report_path = payload
                    self._finish(summary, f"Report: {report_path}")
                elif event == "finished":
                    self._finish(payload, "PDF report was not created")
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _finish(self, summary: TestSummary, suffix: str) -> None:
        if self.timer_job is not None:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        elapsed = int(time.monotonic() - self.test_started_at) if self.test_started_at is not None else 0
        self.test_started_at = None
        self.test_time.set(f"Actual test time: {_format_duration(elapsed)}")
        outcome = "PASSED" if summary.passed else "FAILED"
        self.status.set(f"{outcome} - {suffix}")
        self.start_button.configure(state="normal")
        self.connect_button.configure(state="normal")
        self.stop_button.configure(state="disabled")


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")


def _format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _resource_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parents[2] / "assets" / name


def main() -> None:
    GateCheckerApp().mainloop()