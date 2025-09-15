"""
Event logging for Dados agent execution.
Logs to data/csv/events.csv with rich fields described in README.
"""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class EventLogger:
    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.csv_dir = self.base_dir / "csv"
        self.csv_path = self.csv_dir / "events.csv"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            self._init_csv()

    def _init_csv(self) -> None:
        headers = [
            "timestamp",
            "user_request",
            "generated_commands",
            "mouse_move_from",
            "mouse_click_at",
            "screenshot_before",
            "screenshot_after",
            "execution_success",
            "error_message",
            "execution_time_ms",
            "audio_file",
            "route_path",
        ]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def log(
        self,
        *,
        user_request: str,
        route_path: str,
        generated_commands: Optional[Any] = None,
        mouse_move_from: Optional[Any] = None,
        mouse_click_at: Optional[Any] = None,
        screenshot_before: Optional[str] = None,
        screenshot_after: Optional[str] = None,
        success: bool = True,
        error_message: str = "",
        execution_time_ms: Optional[int] = None,
        audio_file: Optional[str] = None,
    ) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        def _ser(x: Any) -> str:
            if x is None:
                return ""
            try:
                return json.dumps(x)
            except Exception:
                return str(x)
        row = [
            ts,
            user_request,
            _ser(generated_commands),
            _ser(mouse_move_from),
            _ser(mouse_click_at),
            screenshot_before or "",
            screenshot_after or "",
            "1" if success else "0",
            error_message,
            str(execution_time_ms or ""),
            audio_file or "",
            route_path,
        ]
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
