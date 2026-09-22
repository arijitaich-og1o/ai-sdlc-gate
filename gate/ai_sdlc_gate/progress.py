"""Live progress for terminal runs.

Progress is written to stderr only (git shows hook stderr in the developer's terminal) and is never part of the
report. On an interactive terminal a single line is redrawn with a bar, the current phase and pass, the number of
findings so far and the elapsed time; a background ticker keeps the elapsed time and spinner moving while the model
call is in flight so the run never looks frozen. On a non-interactive stream (IDE output panes, CI logs) one plain
line is printed per event instead. Output is ASCII only so every console encoding renders it.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, TextIO

PREFIX = "[ai-sdlc-gate]"
SPINNER = "|/-\\"
BAR_WIDTH = 24
TICK_SECONDS = 0.5


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


class Progress:
    """Progress reporter driven by the runner through small event methods; safe to leave unused."""

    def __init__(self, stream: TextIO | None = None, enabled: bool | None = None, interactive: bool | None = None) -> None:
        self.stream = stream if stream is not None else sys.stderr
        if enabled is None:
            enabled = os.environ.get("AI_SDLC_GATE_NO_PROGRESS", "").strip() not in ("1", "true", "yes")
        self.enabled = bool(enabled)
        if interactive is None:
            try:
                interactive = bool(self.stream.isatty())
            except (AttributeError, ValueError, OSError):
                interactive = False
        self.interactive = bool(interactive)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ticker: threading.Thread | None = None
        self._tick = 0
        self._line_len = 0
        self.started = time.monotonic()
        self.phases: list[tuple[int, str]] = []
        self.phases_done = 0
        self.phase_fraction = 0.0
        self.label = "preparing"
        self.findings = 0
        self._planned = 1
        self._chunks = 1
        self._done_findings = 0
        self._phase_findings = 0
        self.events: list[str] = []  # plain-text log of what happened (tests and non-interactive streams)

    # ------------------------------------------------------------------ events called by the runner

    def start(self, phases: list[tuple[int, str]], files: int) -> None:
        self.phases = list(phases)
        self.started = time.monotonic()
        names = ", ".join(f"{p} {n}" for p, n in self.phases) or "none"
        self._event(f"Reviewing {files} file(s) for phase(s): {names}")
        if self.enabled and self.interactive and self._ticker is None:
            self._ticker = threading.Thread(target=self._run_ticker, name="ai-sdlc-gate-progress", daemon=True)
            self._ticker.start()

    def phase_start(self, phase: int, name: str, chunks: int, planned_passes: int) -> None:
        with self._lock:
            self.phase_fraction = 0.0
            self._planned = max(1, planned_passes)
            self._chunks = max(1, chunks)
            self.label = f"phase {phase} {name}, pass 1 of {self._planned}"
        self._redraw()

    def pass_start(self, phase: int, name: str, n: int, expected: int, chunk: int = 1, chunks: int = 1) -> None:
        with self._lock:
            self._planned = max(self._planned, expected)
            what = "first look" if n == 1 else "looking for what was missed"
            part = f", part {chunk}/{chunks}" if chunks > 1 else ""
            self.label = f"phase {phase} {name}, pass {n} of {self._planned}{part} ({what})"
            # Never show a phase as finished while passes are still running.
            done = (n - 1) * self._chunks + (chunk - 1)
            self.phase_fraction = min(0.95, done / (self._planned * self._chunks))
        self._redraw()

    def pass_done(self, phase: int, name: str, n: int, new_count: int, total_count: int, more: bool) -> None:
        with self._lock:
            self._phase_findings = total_count
            self.findings = self._done_findings + total_count
            if more:
                self._planned = max(self._planned, n + 1)
            self.phase_fraction = min(0.95, n / self._planned) if more else 1.0
        if n == 1:
            found = f"{total_count} finding(s)"
        else:
            found = f"{new_count} more found" if new_count else "nothing new"
        tail = "; taking another look" if more else ""
        self._event(f"phase {phase} ({name}): pass {n} done, {found}{tail}")

    def phase_done(self, phase: int, name: str, findings: int, passes: int, converged: bool, seconds: float, error: str | None = None) -> None:
        with self._lock:
            self._done_findings += findings
            self._phase_findings = 0
            self.phases_done += 1
            self.phase_fraction = 0.0
            self.findings = self._done_findings
        if error:
            self._event(f"phase {phase} ({name}): could not be reviewed ({error[:120]})", persist=True)
            return
        how = "complete, nothing new in the last pass" if converged else "stopped at the pass limit while still finding new issues"
        self._event(f"phase {phase} ({name}): {findings} finding(s) after {passes} pass(es) in {_fmt_duration(seconds)}; {how}", persist=True)

    def finish(self, verdict: str) -> None:
        self._stop.set()
        if self._ticker is not None:
            self._ticker.join(timeout=2)
            self._ticker = None
        self._clear_line()
        self._event(f"Review finished in {_fmt_duration(time.monotonic() - self.started)}: {verdict.upper()}", persist=True)

    # ------------------------------------------------------------------ rendering

    def _overall(self) -> float:
        if not self.phases:
            return 0.0
        return min(0.99, (self.phases_done + self.phase_fraction) / len(self.phases))

    def _event(self, text: str, persist: bool = False) -> None:
        """Record an event; print it as its own line on non-interactive streams (and, when `persist`, on interactive ones too)."""
        self.events.append(text)
        if not self.enabled:
            return
        if not self.interactive or persist:
            with self._lock:
                self._clear_line_locked()
                self._write(f"{PREFIX} {text}\n")
        self._redraw()

    def _redraw(self) -> None:
        if not (self.enabled and self.interactive):
            return
        with self._lock:
            self._redraw_locked()

    def _redraw_locked(self) -> None:
        if self._stop.is_set():
            return
        pct = self._overall()
        filled = int(round(pct * BAR_WIDTH))
        bar = "#" * filled + "." * (BAR_WIDTH - filled)
        spin = SPINNER[self._tick % len(SPINNER)]
        line = (
            f"{PREFIX} [{bar}] {int(pct * 100):3d}%  {self.label}  |  {self.findings} finding(s) so far  |  "
            f"{_fmt_duration(time.monotonic() - self.started)} {spin}"
        )
        pad = " " * max(0, self._line_len - len(line))
        self._write("\r" + line + pad)
        self._line_len = len(line)

    def _clear_line(self) -> None:
        with self._lock:
            self._clear_line_locked()

    def _clear_line_locked(self) -> None:
        if self.enabled and self.interactive and self._line_len:
            self._write("\r" + " " * self._line_len + "\r")
            self._line_len = 0

    def _write(self, text: str) -> None:
        try:
            self.stream.write(text)
            self.stream.flush()
        except (ValueError, OSError):
            self.enabled = False

    def _run_ticker(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            with self._lock:
                self._tick += 1
                self._redraw_locked()


class NoProgress:
    """Null object with the same surface as Progress."""

    events: list[str] = []

    def __getattr__(self, name: str) -> Any:
        return lambda *a, **k: None
