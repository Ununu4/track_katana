import sys
import subprocess
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class SeekSlider(QSlider):
    hoverTimeChanged = pyqtSignal(float)
    seekRequested = pyqtSignal(float)
    dragSeekRequested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setMouseTracking(True)
        self.setTracking(True)
        self._duration = 0.0

    def setDuration(self, duration: float) -> None:
        self._duration = max(0.0, duration)

    def _pos_to_time(self, pos: float) -> float:
        if self._duration <= 0:
            return 0.0
        ratio = max(0.0, min(1.0, pos / max(1, self.width())))
        return ratio * self._duration

    def mouseMoveEvent(self, event):
        if isinstance(event.position(), QPointF):
            hover_time = self._pos_to_time(event.position().x())
            self.hoverTimeChanged.emit(hover_time)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if isinstance(event.position(), QPointF):
            target_time = self._pos_to_time(event.position().x())
            self.seekRequested.emit(target_time)
        super().mousePressEvent(event)

    def sliderChange(self, change):
        super().sliderChange(change)
        if change == QSlider.SliderChange.SliderValueChange and self.isSliderDown():
            seconds = (self.value() / max(1, self.maximum())) * self._duration
            self.dragSeekRequested.emit(seconds)


class AudioChopper(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg WAV Chopper")
        self.audio_path: Optional[Path] = None
        self.duration: float = 0.0
        self.current_time: float = 0.0
        self.play_process: Optional[subprocess.Popen] = None
        self.play_start_monotonic: Optional[float] = None
        self.play_start_position: float = 0.0
        self.chop_start: Optional[float] = None
        self.output_dir: Optional[Path] = None
        self.chop_index: int = 1
        self.ffmpeg_bin = "ffmpeg"
        self.ffprobe_bin = "ffprobe"
        self.ffplay_bin = "ffplay"

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout()

        top_row = QHBoxLayout()
        self.file_label = QLabel("No file loaded")
        open_btn = QPushButton("Load WAV")
        open_btn.clicked.connect(self._choose_file)
        self.output_dir_label = QLabel("Output: not set")
        change_dir_btn = QPushButton("Select output folder")
        change_dir_btn.clicked.connect(self._prompt_output_dir)
        for btn in (open_btn, change_dir_btn):
            btn.setFixedWidth(140)
        top_row.addWidget(open_btn)
        top_row.addWidget(change_dir_btn)
        top_row.addWidget(self.file_label, 1)
        top_row.addWidget(self.output_dir_label, 1)
        main_layout.addLayout(top_row)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.hover_label = QLabel("")
        time_row = QHBoxLayout()
        time_row.addWidget(self.time_label)
        time_row.addStretch()
        time_row.addWidget(self.hover_label)
        main_layout.addLayout(time_row)

        self.slider = SeekSlider()
        self.slider.setRange(0, 10000)
        self.slider.hoverTimeChanged.connect(self._on_hover_time)
        self.slider.seekRequested.connect(self._on_seek)
        self.slider.dragSeekRequested.connect(self._on_slider_drag)
        main_layout.addWidget(self.slider)

        control_row = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setFixedWidth(60)
        self.play_btn.clicked.connect(self._toggle_play)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedWidth(60)
        self.stop_btn.clicked.connect(lambda: self._stop_playback(update_position=True))
        control_row.addWidget(self.play_btn)
        control_row.addWidget(self.stop_btn)
        main_layout.addLayout(control_row)

        chop_box = QGroupBox("Chop controls")
        chop_layout = QGridLayout()

        self.begin_input = QLabel("Begin:")
        self.begin_field = self._build_time_input("hh:mm:ss")
        begin_fill = QPushButton("Set begin to current")
        begin_fill.setFixedWidth(150)
        begin_fill.clicked.connect(self._mark_begin)

        self.end_input = QLabel("End:")
        self.end_field = self._build_time_input("hh:mm:ss")
        end_fill = QPushButton("Set end to current")
        end_fill.setFixedWidth(150)
        end_fill.clicked.connect(self._mark_end)

        export_btn = QPushButton("Export chop")
        export_btn.clicked.connect(self._export_chop)

        chop_layout.addWidget(self.begin_input, 0, 0)
        chop_layout.addWidget(self.begin_field, 0, 1)
        chop_layout.addWidget(begin_fill, 0, 2)
        chop_layout.addWidget(self.end_input, 1, 0)
        chop_layout.addWidget(self.end_field, 1, 1)
        chop_layout.addWidget(end_fill, 1, 2)
        chop_layout.addWidget(export_btn, 2, 0)

        self.chop_list = QListWidget()
        chop_layout.addWidget(self.chop_list, 3, 0, 1, 3)

        chop_box.setLayout(chop_layout)
        main_layout.addWidget(chop_box)

        self.setLayout(main_layout)

    def _build_time_input(self, placeholder: str):
        from PyQt6.QtWidgets import QLineEdit

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setMaximumWidth(120)
        return field

    def _prompt_output_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "Choose folder for chops", str(Path.cwd()))
        if chosen:
            self.output_dir = Path(chosen)
            self.output_dir_label.setText(f"Output: {self.output_dir}")
        else:
            self.output_dir_label.setText("Output: not set")

    def _choose_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select WAV file", str(Path.cwd()), "WAV files (*.wav)")
        if not file_name:
            return
        self.audio_path = Path(file_name)
        self.duration = self._probe_duration(self.audio_path)
        if self.duration <= 0:
            QMessageBox.warning(self, "Invalid file", "Could not read audio duration. Make sure ffprobe is available and the file is valid.")
            return
        self.current_time = 0.0
        self.slider.setDuration(self.duration)
        self._update_time_display(self.current_time)
        self.file_label.setText(f"Loaded: {self.audio_path.name} ({self._format_time(self.duration)})")
        self.chop_start = None
        self.begin_field.clear()
        self.end_field.clear()

    def _probe_duration(self, path: Path) -> float:
        try:
            result = subprocess.run(
                [self.ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip())
        except Exception:
            try:
                import wave

                with wave.open(str(path), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    return frames / float(rate)
            except Exception:
                return 0.0

    def _toggle_play(self):
        if not self.audio_path:
            QMessageBox.information(self, "No file", "Load a WAV file first.")
            return
        if self.play_process:
            self._stop_playback(update_position=True)
        else:
            self._start_playback()

    def _start_playback(self):
        if not self.audio_path:
            return
        if self.current_time >= self.duration:
            self.current_time = 0.0
        self._stop_playback(update_position=False)
        cmd = [
            self.ffplay_bin,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-hide_banner",
            "-vn",
        ]
        if self.current_time > 0:
            cmd += ["-ss", f"{self.current_time:.3f}"]
        cmd += ["-i", str(self.audio_path)]
        try:
            self.play_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            QMessageBox.critical(self, "ffplay not found", "ffplay is required for playback. Ensure FFmpeg is installed and ffplay is on PATH.")
            self.play_process = None
            return
        self.play_start_position = self.current_time
        self.play_start_monotonic = time.monotonic()
        self.play_btn.setText("Stop")
        self.timer.start()

    def _stop_playback(self, update_position: bool):
        if self.play_process:
            self.play_process.kill()
            self.play_process.wait(timeout=2)
            if update_position and self.play_start_monotonic is not None:
                elapsed = time.monotonic() - self.play_start_monotonic
                self.current_time = min(self.duration, self.play_start_position + elapsed)
        self.play_process = None
        self.play_start_monotonic = None
        self.timer.stop()
        self.play_btn.setText("Play")
        self._update_time_display(self.current_time)

    def _tick(self):
        if not self.play_process or self.play_start_monotonic is None:
            return
        elapsed = time.monotonic() - self.play_start_monotonic
        position = min(self.duration, self.play_start_position + elapsed)
        self._update_time_display(position)
        if position >= self.duration or self.play_process.poll() is not None:
            self.current_time = position
            self._stop_playback(update_position=False)

    def _on_hover_time(self, seconds: float):
        self.hover_label.setText(f"Hover: {self._format_time(seconds)}")

    def _on_seek(self, seconds: float):
        if not self.audio_path:
            return
        self.current_time = max(0.0, min(self.duration, seconds))
        if self.play_process:
            self._start_playback()
        else:
            self._update_time_display(self.current_time)

    def _on_slider_drag(self, seconds: float):
        if not self.audio_path:
            return
        self.current_time = max(0.0, min(self.duration, seconds))
        if self.play_process:
            self._start_playback()
        self._update_time_display(self.current_time)

    def _mark_begin(self):
        t = self._current_display_time()
        self.begin_field.setText(self._format_time(t))
        self.chop_start = t

    def _mark_end(self):
        t = self._current_display_time()
        self.end_field.setText(self._format_time(t))

    def _export_chop(self):
        if not self.audio_path:
            QMessageBox.information(self, "No file", "Load a WAV file first.")
            return
        if self.output_dir is None:
            QMessageBox.information(self, "No folder", "Choose an output folder for chops first.")
            return
        try:
            start_time = self._parse_time(self.begin_field.text())
            end_time = self._parse_time(self.end_field.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid time", str(exc))
            return
        if end_time <= start_time:
            QMessageBox.warning(self, "Invalid range", "End time must be after begin time.")
            return
        output_name = f"chop_{self.chop_index:03d}.wav"
        output_path = self.output_dir / output_name
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-hwaccel",
            "auto",
            "-hwaccel_output_format",
            "cuda",
            "-ss",
            f"{start_time:.3f}",
            "-to",
            f"{end_time:.3f}",
            "-i",
            str(self.audio_path),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode(errors="ignore"))
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", f"Could not export chop: {exc}")
            return
        self.chop_list.addItem(f"{output_name} ({self._format_time(start_time)} - {self._format_time(end_time)})")
        self.chop_index += 1
        self.begin_field.clear()
        self.end_field.clear()

    def _current_display_time(self) -> float:
        if self.play_process and self.play_start_monotonic is not None:
            return min(self.duration, self.play_start_position + (time.monotonic() - self.play_start_monotonic))
        return self.current_time

    def _update_time_display(self, seconds: float):
        seconds = max(0.0, min(self.duration, seconds))
        self.slider.blockSignals(True)
        if self.duration > 0:
            ratio = seconds / self.duration
            self.slider.setValue(int(ratio * self.slider.maximum()))
        self.slider.blockSignals(False)
        self.time_label.setText(f"{self._format_time(seconds)} / {self._format_time(self.duration)}")
        self.current_time = seconds

    @staticmethod
    def _format_time(seconds: float) -> str:
        seconds = max(0.0, seconds)
        total_centiseconds = int(round(seconds * 100))
        h = total_centiseconds // (3600 * 100)
        m = (total_centiseconds // (60 * 100)) % 60
        s = (total_centiseconds // 100) % 60
        cs = total_centiseconds % 100
        return f"{h:02d}:{m:02d}:{s:02d}:{cs:02d}"

    @staticmethod
    def _parse_time(text: str) -> float:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Enter begin and end times as hh:mm:ss")
        parts = cleaned.split(":")
        if len(parts) == 2:
            m, s = parts
            h = 0
            cs = 0
        elif len(parts) == 3:
            h, m, s = parts
            cs = 0
        elif len(parts) == 4:
            h, m, s, cs = parts
        else:
            raise ValueError("Use hh:mm:ss or hh:mm:ss:cc format")
        try:
            h = int(h)
            m = int(m)
            s = int(s)
            cs = int(float(cs))
        except ValueError:
            raise ValueError("Times must be numeric (hh:mm:ss:cc)") from None
        total = h * 3600 + m * 60 + s + cs / 100.0
        if total < 0:
            raise ValueError("Time cannot be negative")
        return total


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioChopper()
    window.resize(700, 400)
    window.show()
    sys.exit(app.exec())
