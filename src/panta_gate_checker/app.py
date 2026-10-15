from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from math import ceil
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
        self.geometry("940x800")
        self.minsize(780, 700)
        self.configure(bg="#F3F1EA")
        icon_path = _resource_path("PantaGateChecker.ico")
        if icon_path.exists():
            self.iconbitmap(default=str(icon_path))

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None

        self.endpoint = tk.StringVar(value=DEFAULT_PANDORA_ENDPOINT)
        self.test_name = tk.StringVar(value=DEFAULT_TEST_NAME)
        self.operator_name = tk.StringVar()
        self.cycles = tk.StringVar(value="50")
        self.cancel_percent = tk.StringVar(value="10")
        self.expert_mode = tk.BooleanVar(value=False)
        self.expert_fields: list[ttk.Entry] = []
        self.output_directory = tk.StringVar(value=str(DEFAULT_OUTPUT_DIRECTORY))
        self.device_name = tk.StringVar(value="Not connected")
        self.status = tk.StringVar(value="Ready to start")
        self.test_time = tk.StringVar()
        self.total_cycles = tk.StringVar(value="Total 0")
        self.passed_cycles = tk.StringVar(value="Passed 0")
        self.failed_cycles = tk.StringVar(value="Failed 0")
        self.test_started_at: float | None = None
        self.requested_cycles: int | None = None
        self.cycle_durations: list[float] = []
        self.timer_job: str | None = None
        self.estimate_deadline: float | None = None
        self.report_path: Path | None = None

        self._configure_styles()
        self._build_ui()
        self.after(100, self._process_events)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#F4F5F2")
        style.configure("Panel.TFrame", background="#FFFFFF")
        style.configure("TLabel", background="#F4F5F2", foreground="#25332E", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#FFFFFF", foreground="#25332E", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#153F35", foreground="#FFFFFF", font=("Segoe UI", 26, "bold"))
        style.configure("Tagline.TLabel", background="#153F35", foreground="#D7E7DE", font=("Segoe UI", 11))
        style.configure("Section.TLabel", background="#FFFFFF", foreground="#153F35", font=("Segoe UI", 13, "bold"))
        style.configure("Summary.TLabel", background="#FFFFFF", foreground="#52625B", font=("Segoe UI", 9, "bold"))
        style.configure("PassedSummary.TLabel", background="#FFFFFF", foreground="#16803C", font=("Segoe UI", 9, "bold"))
        style.configure("FailedSummary.TLabel", background="#FFFFFF", foreground="#C62828", font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", background="#D97A32", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"), padding=(16, 7))
        style.map("Accent.TButton", background=[("active", "#B95F21"), ("disabled", "#C9C5BE")])
        style.configure("Stop.TButton", background="#B94A48", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"), padding=(16, 7))
        style.map(
            "Stop.TButton",
            background=[("active", "#9F3837"), ("disabled", "#D8DAD8")],
            foreground=[("disabled", "#777F7B")],
        )
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("Panel.TCheckbutton", background="#FFFFFF", foreground="#25332E", font=("Segoe UI", 10))
        style.configure(
            "TEntry",
            font=("Segoe UI", 10),
            padding=(8, 6),
            fieldbackground="#FFFFFF",
            foreground="#25332E",
            bordercolor="#D5DDD8",
            insertcolor="#25332E",
        )
        style.map("TEntry", fieldbackground=[("disabled", "#F0F2F0")])
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=29, background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#25332E")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#EEF1EF", foreground="#153F35", padding=(8, 8), relief="flat")
        style.map("Treeview.Heading", background=[("active", "#E4EAE6")])
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#E6EAE7",
            background="#16803C",
            bordercolor="#E6EAE7",
            lightcolor="#16803C",
            darkcolor="#16803C",
        )

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg="#153F35", height=132)
        header.pack(fill="x")
        header.pack_propagate(False)

        product_image_path = _resource_path("prometheus-panta.webp")
        if product_image_path.exists():
            with Image.open(product_image_path) as product_image:
                fitted_image = ImageOps.fit(
                    product_image.convert("RGB"),
                    (280, 132),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.45, 0.5),
                )
            self.product_photo = ImageTk.PhotoImage(fitted_image)
            tk.Label(header, image=self.product_photo, bg="#153F35", borderwidth=0).pack(side="right")

        title_area = tk.Frame(header, bg="#153F35")
        title_area.pack(side="left", fill="both", expand=True)
        ttk.Label(title_area, text="Panta Gate Checker", style="Title.TLabel").pack(anchor="w", padx=28, pady=(26, 1))
        ttk.Label(title_area, text="Automated gate stress testing", style="Tagline.TLabel").pack(anchor="w", padx=30)

        content = ttk.Frame(self, padding=24)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        settings = ttk.Frame(content, style="Panel.TFrame", padding=14)
        settings.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        settings.columnconfigure(0, weight=1)
        settings.columnconfigure(1, weight=1)

        device_row = ttk.Frame(settings, style="Panel.TFrame")
        device_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        device_row.columnconfigure(2, weight=1)
        self.connection_indicator = tk.Canvas(
            device_row,
            width=12,
            height=12,
            bg="#FFFFFF",
            highlightthickness=0,
            borderwidth=0,
        )
        self.connection_indicator.grid(row=0, column=0, padx=(1, 9))
        self.connection_indicator.create_oval(2, 2, 10, 10, fill="#8B9490", outline="")
        ttk.Label(device_row, text="Device name / serial", style="Panel.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(
            device_row,
            textvariable=self.device_name,
            style="Panel.TLabel",
            font=("Segoe UI", 11, "bold"),
            foreground="#153F35",
        ).grid(row=0, column=2, sticky="w", padx=14)
        self.connect_button = ttk.Button(device_row, text="Check device", command=self._check_device)
        self.connect_button.grid(row=0, column=3, sticky="e")

        device_section = ttk.Frame(settings, style="Panel.TFrame", padding=(12, 10))
        device_section.grid(row=1, column=0, sticky="nsew", padx=(0, 7))
        device_section.columnconfigure(0, weight=1)
        ttk.Label(device_section, text="Device Configuration", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.expert_fields = [
            self._field(device_section, "Panta IP Adresse", self.endpoint, 0, 0, row_offset=1),
            self._field(device_section, "Number of cycles", self.cycles, 1, 0, row_offset=1),
        ]

        test_section = ttk.Frame(settings, style="Panel.TFrame", padding=(12, 10))
        test_section.grid(row=1, column=1, sticky="nsew", padx=(7, 0))
        test_section.columnconfigure(0, weight=1)
        ttk.Label(test_section, text="Test Configuration", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.expert_fields.extend(
            [
                self._field(test_section, "Test Name", self.test_name, 0, 0, row_offset=1),
                self._field(test_section, "Cancellation Probability (%)", self.cancel_percent, 1, 0, row_offset=1),
            ]
        )
        ttk.Checkbutton(
            test_section,
            text="Expert Mode",
            variable=self.expert_mode,
            command=self._set_expert_mode,
            style="Panel.TCheckbutton",
        ).grid(row=6, column=0, sticky="w", pady=(10, 0))

        operator_section = ttk.Frame(settings, style="Panel.TFrame", padding=(12, 10))
        operator_section.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        operator_section.columnconfigure(0, weight=1)
        operator_section.columnconfigure(1, weight=2)
        ttk.Label(operator_section, text="Operator & Report", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        operator_field = ttk.Frame(operator_section, style="Panel.TFrame")
        operator_field.grid(row=1, column=0, sticky="ew", padx=(0, 12))
        operator_field.columnconfigure(0, weight=1)
        self._field(operator_field, "Operator name", self.operator_name, 0, 0)

        report_field = ttk.Frame(operator_section, style="Panel.TFrame")
        report_field.grid(row=1, column=1, sticky="ew")
        report_field.columnconfigure(0, weight=1)
        ttk.Label(report_field, text="Report folder", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        report_row = ttk.Frame(report_field, style="Panel.TFrame")
        report_row.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        report_row.columnconfigure(0, weight=1)
        ttk.Entry(report_row, textvariable=self.output_directory).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(report_row, text="Browse...", command=self._choose_output_directory).grid(row=0, column=1, sticky="e")
        self._set_expert_mode()

        results_frame = ttk.Frame(content, style="Panel.TFrame", padding=14)
        results_frame.grid(row=1, column=0, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        top_line = ttk.Frame(results_frame, style="Panel.TFrame")
        top_line.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_line.columnconfigure(0, weight=1)
        ttk.Label(top_line, text="Cycle results", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        summary_frame = ttk.Frame(top_line, style="Panel.TFrame")
        summary_frame.grid(row=0, column=1, sticky="e")
        ttk.Label(summary_frame, textvariable=self.total_cycles, style="Summary.TLabel").pack(side="left", padx=(0, 14))
        ttk.Label(summary_frame, textvariable=self.passed_cycles, style="PassedSummary.TLabel").pack(side="left", padx=(0, 14))
        ttk.Label(summary_frame, textvariable=self.failed_cycles, style="FailedSummary.TLabel").pack(side="left")

        columns = ("cycle", "operation", "result", "details")
        self.results = ttk.Treeview(results_frame, columns=columns, show="headings")
        self.results.heading("cycle", text="Cycle")
        self.results.heading("operation", text="Operation")
        self.results.heading("result", text="Result")
        self.results.heading("details", text="Details")
        self.results.column("cycle", width=70, stretch=False, anchor="center")
        self.results.column("operation", width=150, stretch=False, anchor="w")
        self.results.column("result", width=85, stretch=False, anchor="center")
        self.results.column("details", width=440, minwidth=240, stretch=True, anchor="w")
        self.results.tag_configure("pass_even", background="#FFFFFF", foreground="#16803C")
        self.results.tag_configure("pass_odd", background="#F6F8F6", foreground="#16803C")
        self.results.tag_configure("fail_even", background="#FFFFFF", foreground="#C62828")
        self.results.tag_configure("fail_odd", background="#F6F8F6", foreground="#C62828")
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results.yview)
        self.results.configure(yscrollcommand=scrollbar.set)
        self.results.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        footer = ttk.Frame(content)
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        status_row = ttk.Frame(footer)
        status_row.grid(row=0, column=0, sticky="ew")
        status_row.columnconfigure(0, weight=1)
        ttk.Label(status_row, textvariable=self.status).grid(row=0, column=0, sticky="w")
        ttk.Label(status_row, textvariable=self.test_time, foreground="#65736D").grid(
            row=0, column=1, sticky="e", padx=(12, 18)
        )
        self.stop_button = ttk.Button(status_row, text="Stop", style="Stop.TButton", command=self._stop, state="disabled")
        self.open_test_folder_button = ttk.Button(
            status_row,
            text="Open Test Folder",
            command=self._open_test_folder,
            state="disabled",
        )
        self.open_test_folder_button.grid(row=0, column=2, padx=(0, 8))
        self.stop_button.grid(row=0, column=3, padx=(0, 8))
        self.start_button = ttk.Button(status_row, text="Start test", style="Accent.TButton", command=self._start)
        self.start_button.grid(row=0, column=4)
        self.progress = ttk.Progressbar(
            footer,
            orient="horizontal",
            mode="determinate",
            maximum=1,
            value=0,
        )
        self.progress.grid(row=1, column=0, sticky="ew", pady=(9, 0))

    def _field(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        column: int,
        row_offset: int = 0,
    ) -> ttk.Entry:
        label_row = row_offset + row * 2
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(
            row=label_row, column=column, sticky="w", pady=(0 if row == 0 else 12, 0)
        )
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=label_row + 1, column=column, sticky="ew", pady=(4, 0))
        return entry

    def _set_connection_indicator(self, color: str) -> None:
        self.connection_indicator.itemconfigure("all", fill=color)

    def _update_result_summary(self) -> None:
        total = 0
        passed = 0
        failed = 0
        for item in self.results.get_children():
            values = self.results.item(item, "values")
            if len(values) < 3:
                continue
            total += 1
            result = str(values[2]).upper()
            if result in {"PASS", "PASSED"}:
                passed += 1
            elif result in {"FAIL", "FAILED"}:
                failed += 1
        self.total_cycles.set(f"Total {total}")
        self.passed_cycles.set(f"Passed {passed}")
        self.failed_cycles.set(f"Failed {failed}")

    def _set_expert_mode(self) -> None:
        state = "normal" if self.expert_mode.get() else "disabled"
        for field in self.expert_fields:
            field.configure(state=state)

    def _choose_output_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_directory.get())
        if selected:
            self.output_directory.set(selected)

    def _update_time_estimate(self) -> None:
        if self.test_started_at is not None:
            if self.estimate_deadline is None:
                self.test_time.set("Calculating remaining time...")
            else:
                remaining = max(0, ceil(self.estimate_deadline - time.monotonic()))
                self.test_time.set(f"Estimated remaining time: {_format_countdown(remaining)}")
            return
        self.test_time.set("")

    def _check_device(self) -> None:
        endpoint = self.endpoint.get().strip()
        if not endpoint:
            messagebox.showerror("Invalid settings", "Pandora endpoint is required", parent=self)
            return

        self._set_connection_indicator("#E28A2B")
        self.device_name.set("Connecting...")
        self.status.set("Connecting to device...")
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
            if (
                not self.endpoint.get().strip()
                or not self.test_name.get().strip()
                or not self.operator_name.get().strip()
            ):
                raise ValueError("Endpoint, test name, and operator name are required")
        except ValueError as error:
            messagebox.showerror("Invalid settings", str(error), parent=self)
            return

        for item in self.results.get_children():
            self.results.delete(item)
        self._update_result_summary()
        self.stop_event.clear()
        self.report_path = None
        self.open_test_folder_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._set_connection_indicator("#E28A2B")
        self.device_name.set("Connecting...")
        self.status.set("Connecting to device...")
        self.test_started_at = time.monotonic()
        self.requested_cycles = cycles
        self.progress.configure(maximum=cycles, value=0)
        self.cycle_durations.clear()
        self.estimate_deadline = None
        self._tick_timer()
        endpoint = self.endpoint.get().strip()
        test_name = self.test_name.get().strip()
        operator_name = self.operator_name.get().strip()
        output_directory = self.output_directory.get()
        self.worker = threading.Thread(
            target=self._run_test,
            args=(cycles, cancel_probability, endpoint, test_name, operator_name, output_directory),
            daemon=True,
        )
        self.worker.start()

    def _run_test(
        self,
        cycles: int,
        cancel_probability: float,
        endpoint: str,
        test_name: str,
        operator_name: str,
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
            report_path = create_pdf_report(
                summary,
                Path(output_directory) / report_name,
                operator_name,
            )
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
        self._update_time_estimate()
        self.timer_job = self.after(1000, self._tick_timer)

    def _recalculate_time_estimate(self) -> None:
        if self.test_started_at is None or self.requested_cycles is None:
            self.estimate_deadline = None
            return
        elapsed = max(0.0, time.monotonic() - self.test_started_at)
        remaining = _estimate_remaining_seconds(
            elapsed,
            len(self.cycle_durations),
            self.requested_cycles,
        )
        self.estimate_deadline = time.monotonic() + remaining if remaining is not None else None

    def _process_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "connected":
                    self.device_name.set(str(payload))
                    self._set_connection_indicator("#16803C")
                    self.status.set(f"Running cycle 1 of {self.requested_cycles or 1}")
                elif event == "device_checked":
                    self.device_name.set(str(payload))
                    self._set_connection_indicator("#16803C")
                    self.status.set("Device connected")
                    self.connect_button.configure(state="normal")
                elif event == "device_error":
                    self.device_name.set("Connection failed")
                    self._set_connection_indicator("#C62828")
                    self.status.set(f"Error occurred: {payload}")
                    self.connect_button.configure(state="normal")
                elif event == "result":
                    result = payload
                    if isinstance(result, CycleResult):
                        self.cycle_durations.append(
                            (result.finished_at - result.started_at).total_seconds()
                        )
                        self._recalculate_time_estimate()
                        self._update_time_estimate()
                        row_number = len(self.results.get_children())
                        outcome = "PASS" if result.passed else "FAIL"
                        self.results.insert(
                            "",
                            "end",
                            values=(
                                result.number,
                                "Open cancelled" if result.cancelled else "Open / close",
                                outcome,
                                result.message,
                            ),
                            tags=(
                                f"{'pass' if result.passed else 'fail'}_"
                                f"{'even' if row_number % 2 == 0 else 'odd'}",
                            ),
                        )
                        completed = len(self.results.get_children())
                        self.progress.configure(value=completed)
                        self._update_result_summary()
                        if self.stop_event.is_set():
                            self.status.set("Stopping after returning the gate to a safe state...")
                        elif self.requested_cycles is not None:
                            next_cycle = min(completed + 1, self.requested_cycles)
                            self.status.set(f"Running cycle {next_cycle} of {self.requested_cycles}")
                elif event == "error":
                    self.status.set(f"Error occurred: {payload}")
                elif event == "complete":
                    summary, report_path = payload
                    self._finish(summary, f"Report: {report_path}", Path(report_path))
                elif event == "finished":
                    self._finish(payload, "PDF report was not created")
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _finish(self, summary: TestSummary, suffix: str, report_path: Path | None = None) -> None:
        if self.timer_job is not None:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.report_path = report_path
        self.open_test_folder_button.configure(state="normal")
        self.test_started_at = None
        self.estimate_deadline = None
        if summary.error_message or suffix == "PDF report was not created":
            self.test_time.set("Error occurred")
            error = summary.error_message or suffix
            self.status.set(f"Error occurred: {error}")
            self._set_connection_indicator("#C62828")
        elif self.stop_event.is_set() and len(summary.results) < summary.requested_cycles:
            self.test_time.set("Test stopped")
            self.status.set(
                f"Test stopped — {len(summary.results)} of {summary.requested_cycles} cycles completed | {suffix}"
            )
        else:
            self.test_time.set("Test completed")
            outcome = "PASSED" if summary.passed else "FAILED"
            self.status.set(f"Test completed — {outcome} | {suffix}")
        self.start_button.configure(state="normal")
        self.connect_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def _open_test_folder(self) -> None:
        if self.report_path is None:
            messagebox.showinfo(
                "Report unavailable",
                "No report was generated for the completed test.",
                parent=self,
            )
            return

        try:
            if not self.report_path.parent.is_dir():
                messagebox.showerror(
                    "Folder unavailable",
                    f"The report folder could not be found:\n{self.report_path.parent}",
                    parent=self,
                )
                return
            if not self.report_path.is_file():
                messagebox.showerror(
                    "Report unavailable",
                    f"The report file could not be found:\n{self.report_path}",
                    parent=self,
                )
                return
            subprocess.Popen(["explorer.exe", "/select,", str(self.report_path)])
        except OSError as error:
            messagebox.showerror(
                "Could not open report folder",
                f"Windows File Explorer could not open the report folder:\n{error}",
                parent=self,
            )


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")


def _format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _format_countdown(total_seconds: int) -> str:
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _estimate_remaining_seconds(
    elapsed_seconds: float,
    completed_cycles: int,
    requested_cycles: int,
) -> int | None:
    if completed_cycles < 2:
        return None
    remaining_cycles = max(0, requested_cycles - completed_cycles)
    average_cycle_duration = max(0.0, elapsed_seconds) / completed_cycles
    return max(0, round(average_cycle_duration * remaining_cycles))


def _resource_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parents[2] / "assets" / name


def main() -> None:
    GateCheckerApp().mainloop()