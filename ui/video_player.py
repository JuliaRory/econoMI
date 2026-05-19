import os
import random
from datetime import datetime

from PyQt5.QtCore import QElapsedTimer, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QApplication, QLabel, QWidget


MESSAGE_LABEL_STYLE = "color: white; background: rgba(0, 0, 0, 110); padding: 24px; font-size: 28pt; font-weight: 700;"
RESULT_LABEL_STYLE = "color: white; background: rgba(0, 0, 0, 150); padding: 8px; font-size: 72pt; font-weight: 800;"


class HandStimuliPresentation(QWidget):
    stimuliStarted = pyqtSignal()
    stimuliFinished = pyqtSignal()
    stimuliPaused = pyqtSignal()
    currIdxChanged = pyqtSignal(int)
    stimulusShown = pyqtSignal(str)
    responseCaptured = pyqtSignal(dict)
    trialFinished = pyqtSignal(dict)

    def __init__(self, settings, stimuli_files=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._stimuli_files = list(stimuli_files or [])
        self._trial_results = []

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_phase_timeout)

        self._clock = QElapsedTimer()
        self._stimulus_clock = QElapsedTimer()
        self._phase = "idle"
        self._phase_remaining_ms = 0
        self._phase_deadline_ms = 0
        self._current_index = -1
        self._current_isi_ms = 0
        self._paused = False
        self._started = False
        self._finished = False
        self._current_stimulus = ""
        self._response_for_current_trial = None
        self._final_pixmap = QPixmap()

        self.setWindowTitle("econoMI stimuli")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.BlankCursor)

        self._background_pixmap = QPixmap(self.settings.background_image)
        self._stimulus_background_pixmap = QPixmap(getattr(self.settings, "stimulus_background_image", ""))
        self._cross_pixmap = QPixmap(self.settings.cross_image)
        self._welcome_pixmap = QPixmap(getattr(self.settings, "welcome_image", ""))
        self._intro_video_path = os.path.abspath(getattr(self.settings, "intro_video", ""))

        self._background_label = QLabel(self)
        self._background_label.setAlignment(Qt.AlignCenter)
        self._background_label.setStyleSheet("background: black;")

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._image_label.setStyleSheet("background: transparent;")

        self._message_label = QLabel(self)
        self._message_label.setAlignment(Qt.AlignCenter)
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(MESSAGE_LABEL_STYLE)
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        self._message_label.setFont(font)
        self._message_label.hide()

        self._intro_video_widget = QVideoWidget(self)
        self._intro_video_widget.hide()
        self._intro_marker_label = QLabel(self)
        self._intro_marker_label.setFixedSize(80, 80)
        self._intro_marker_label.setStyleSheet("background: white;")
        self._intro_marker_label.hide()
        self._final_marker_label = QLabel(self)
        self._final_marker_label.setFixedSize(80, 80)
        self._final_marker_label.setStyleSheet("background: white;")
        self._final_marker_label.hide()
        self._intro_player = QMediaPlayer(self)
        self._intro_player.setVideoOutput(self._intro_video_widget)
        self._intro_player.mediaStatusChanged.connect(self._on_intro_media_status_changed)

        self._set_monitor()
        self._show_blank()

    @property
    def is_paused(self):
        return self._paused

    @property
    def is_started(self):
        return self._started

    @property
    def trial_results(self):
        return list(self._trial_results)

    def set_stimuli_files(self, stimuli_files):
        if self._started:
            return
        self._stimuli_files = list(stimuli_files or [])
        self._current_index = -1
        self._current_stimulus = ""
        self._trial_results = []
        self._response_for_current_trial = None

    def start_or_pause(self):
        if self._finished:
            return
        if not self._started:
            self._started = True
            self._clock.start()
            self.stimuliStarted.emit()
            self._start_intro_video()
            return
        self._toggle_pause()

    def pause_video(self):
        self.start_or_pause()

    def finish(self):
        self._timer.stop()
        self._stop_intro_video()
        if self._finished:
            self.close()
            return
        self._finished = True
        self.stimuliFinished.emit()
        self.close()

    def restart_sequence(self):
        self._timer.stop()
        self._trial_results = []
        self._current_index = -1
        self._paused = False
        self._started = False
        self._finished = False
        self._phase = "idle"
        self._response_for_current_trial = None
        self._final_pixmap = QPixmap()
        self._stop_intro_video()
        self._show_blank()

    def show_result_percentage(self, percent):
        self._message_label.setStyleSheet(RESULT_LABEL_STYLE)
        font = self._message_label.font()
        font.setPointSize(80)
        font.setBold(True)
        self._message_label.setFont(font)
        self._message_label.setText(f"Корректно: {percent:.0f}%")
        self._message_label.show()
        self._message_label.raise_()

    def _set_monitor(self):
        screens = QApplication.instance().screens()
        if not screens:
            raise RuntimeError("No Qt screens are available.")
        monitor_index = min(max(int(self.settings.monitor) - 1, 0), len(screens) - 1)
        screen = screens[monitor_index]
        self.create()
        window = self.windowHandle()
        if window is not None:
            window.setScreen(screen)
        self.move(screen.geometry().topLeft())
        self.setGeometry(screen.geometry())
        self.showFullScreen()

    def _start_intro_video(self):
        if not os.path.isfile(self._intro_video_path):
            self._start_next_trial()
            return
        self._phase = "intro_video"
        self._phase_remaining_ms = 0
        self._phase_deadline_ms = self._clock.elapsed()
        self._show_blank()
        self._intro_video_widget.setGeometry(self.rect())
        self._intro_video_widget.show()
        self._intro_video_widget.raise_()
        self._position_intro_marker()
        self._intro_marker_label.show()
        self._intro_marker_label.raise_()
        self._intro_player.setMedia(QMediaContent(QUrl.fromLocalFile(self._intro_video_path)))
        self._intro_player.play()

    def _stop_intro_video(self):
        self._intro_player.stop()
        self._intro_video_widget.hide()
        self._intro_marker_label.hide()

    def _on_intro_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia and self._phase == "intro_video" and not self._finished:
            self._intro_video_widget.hide()
            self._intro_marker_label.hide()
            self._start_next_trial()

    def _position_intro_marker(self):
        margin = 0
        self._intro_marker_label.move(self.width() - self._intro_marker_label.width() - margin, margin)

    def _position_final_marker(self):
        margin = 0
        self._final_marker_label.move(self.width() - self._final_marker_label.width() - margin, margin)

    def _start_next_trial(self):
        self._current_index += 1
        if self._current_index >= len(self._stimuli_files):
            self._finish_sequence()
            return

        self._response_for_current_trial = None
        self._current_stimulus = self._stimuli_files[self._current_index]
        self.currIdxChanged.emit(self._current_index + 1)
        self._current_isi_ms = self._next_cross_duration_ms()
        self._start_phase("cross", self._current_isi_ms)

    def _next_cross_duration_ms(self):
        return self._next_duration_ms(
            fixed_s=getattr(self.settings, "isi_s", 1.5),
            range_enabled=getattr(self.settings, "isi_range_enabled", False),
            min_s=getattr(self.settings, "isi_min_s", getattr(self.settings, "isi_s", 1.5)),
            max_s=getattr(self.settings, "isi_max_s", getattr(self.settings, "isi_s", 1.5)),
        )

    def _next_blank_duration_ms(self):
        fallback_s = float(getattr(self.settings, "blank_ms", 500)) / 1000.0
        return self._next_duration_ms(
            fixed_s=getattr(self.settings, "blank_s", fallback_s),
            range_enabled=getattr(self.settings, "blank_range_enabled", False),
            min_s=getattr(self.settings, "blank_min_s", fallback_s),
            max_s=getattr(self.settings, "blank_max_s", fallback_s),
        )

    @staticmethod
    def _next_duration_ms(fixed_s, range_enabled, min_s, max_s):
        if not range_enabled:
            return int(round(float(fixed_s) * 1000))

        min_s = float(min_s)
        max_s = float(max_s)
        if max_s < min_s:
            min_s, max_s = max_s, min_s
        if min_s == max_s:
            return int(round(min_s * 1000))
        return int(round(random.uniform(min_s, max_s) * 1000))

    def _start_phase(self, phase, duration_ms):
        self._intro_video_widget.hide()
        self._intro_marker_label.hide()
        self._final_marker_label.hide()
        self._phase = phase
        self._phase_remaining_ms = max(0, int(duration_ms))
        self._phase_deadline_ms = self._clock.elapsed() + self._phase_remaining_ms
        self._update_background()

        if phase == "cross":
            self._show_centered_pixmap(self._cross_pixmap)
        elif phase == "welcome":
            self._show_fit_pixmap(self._welcome_pixmap)
        elif phase == "stimulus":
            pixmap = QPixmap(self._current_stimulus)
            self._show_centered_pixmap(pixmap)
            self._stimulus_clock.restart()
            self.stimulusShown.emit(self._current_stimulus)
        elif phase == "blank":
            self._show_blank()

        self._timer.start(self._phase_remaining_ms)

    def _on_phase_timeout(self):
        if self._paused:
            return
        if self._phase == "cross":
            self._start_phase("stimulus", self.settings.stimulus_ms)
        elif self._phase == "welcome":
            self._start_next_trial()
        elif self._phase == "stimulus":
            self._finish_trial()
        elif self._phase == "blank":
            self._start_next_trial()

    def _finish_trial(self):
        result = self._build_trial_result(self._response_for_current_trial)
        self._trial_results.append(result)
        self.trialFinished.emit(result)
        self._start_phase("blank", self._next_blank_duration_ms())

    def _finish_sequence(self):
        self._timer.stop()
        self._finished = True
        self._phase = "finished"
        self._show_final_image()
        self.stimuliFinished.emit()

    def _show_final_image(self):
        self._final_pixmap = self._random_final_pixmap()
        if self._final_pixmap.isNull():
            self._show_blank()
            return
        self._update_background()
        self._show_fit_pixmap(self._final_pixmap)
        self._position_final_marker()
        self._final_marker_label.show()
        self._final_marker_label.raise_()

    def _random_final_pixmap(self):
        folder = getattr(self.settings, "final_images_folder", "")
        if not os.path.isdir(folder):
            return QPixmap()
        extensions = {ext.lower() for ext in getattr(self.settings, "extensions", [])}
        image_paths = [
            os.path.join(folder, filename)
            for filename in os.listdir(folder)
            if os.path.splitext(filename)[1].lower() in extensions
        ]
        if not image_paths:
            return QPixmap()
        return QPixmap(random.choice(image_paths))

    def _toggle_pause(self):
        if self._phase == "intro_video":
            if self._paused:
                self._paused = False
                self._intro_player.play()
            else:
                self._paused = True
                self._intro_player.pause()
            self.stimuliPaused.emit()
            return

        if self._paused:
            self._paused = False
            self._phase_deadline_ms = self._clock.elapsed() + self._phase_remaining_ms
            self._timer.start(self._phase_remaining_ms)
        else:
            self._paused = True
            self._phase_remaining_ms = max(0, self._phase_deadline_ms - self._clock.elapsed())
            self._timer.stop()
        self.stimuliPaused.emit()

    def _build_trial_result(self, response):
        correct_answer = self._correct_answer_from_filename(self._current_stimulus)
        response_key = None if response is None else response["response"]
        rt_ms = None if response is None else response["rt_ms"]
        is_correct = response_key is not None and correct_answer == response_key

        return {
            "trial_index": self._current_index + 1,
            "stimulus": os.path.basename(self._current_stimulus),
            "correct_answer": correct_answer,
            "response": response_key,
            "rt_ms": rt_ms,
            "isi_ms": self._current_isi_ms,
            "is_correct": is_correct,
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        }

    @staticmethod
    def _correct_answer_from_filename(path):
        name = os.path.basename(path)
        if not name:
            return None
        stem = os.path.splitext(name)[0]
        parts = stem.replace("-", "_").split("_")
        for part in parts:
            normalized = part.lower()
            if normalized == "same":
                return "Same"
            if normalized == "mirror":
                return "Mirror"
        first = name[0].upper()
        if first in {"L", "R"}:
            return first
        for part in parts:
            part = part.upper()
            if part in {"L", "R"}:
                return part
        return None

    def _show_blank(self):
        if hasattr(self, "_intro_video_widget"):
            self._intro_video_widget.hide()
        if hasattr(self, "_intro_marker_label"):
            self._intro_marker_label.hide()
        if hasattr(self, "_final_marker_label"):
            self._final_marker_label.hide()
        self._message_label.hide()
        self._image_label.clear()
        self._image_label.hide()

    def _show_centered_pixmap(self, pixmap):
        self._message_label.hide()
        if pixmap.isNull():
            self._image_label.clear()
            self._image_label.hide()
            return
        self._image_label.setPixmap(pixmap)
        self._image_label.resize(pixmap.size())
        self._image_label.move((self.width() - pixmap.width()) // 2, (self.height() - pixmap.height()) // 2)
        self._image_label.show()
        self._image_label.raise_()

    def _show_fit_pixmap(self, pixmap):
        if pixmap.isNull():
            self._image_label.clear()
            self._image_label.hide()
            return
        scaled = pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._show_centered_pixmap(scaled)

    def _update_background(self):
        pixmap = self._current_background_pixmap()
        if pixmap.isNull():
            self._background_label.setGeometry(self.rect())
            return
        scaled = pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self._background_label.setPixmap(scaled)
        self._background_label.setGeometry(self.rect())

    def _current_background_pixmap(self):
        if self._phase == "stimulus" and not self._stimulus_background_pixmap.isNull():
            return self._stimulus_background_pixmap
        return self._background_pixmap

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return

        if event.key() == Qt.Key_Space:
            self.start_or_pause()
            return
        if event.key() == Qt.Key_Escape:
            self.finish()
            return

        if self._phase == "stimulus" and event.key() in (Qt.Key_Left, Qt.Key_Right):
            response = self._response_from_key(event.key())
            self._response_for_current_trial = {
                "response": response,
                "rt_ms": int(self._stimulus_clock.elapsed()),
            }
            self.responseCaptured.emit(self._build_trial_result(self._response_for_current_trial))
            self._timer.stop()
            self._finish_trial()
            return

        super().keyPressEvent(event)

    def _response_from_key(self, key):
        if int(getattr(self.settings, "stimulus_type_curr", 0)) == 1:
            return "Mirror" if key == Qt.Key_Left else "Same"
        return "L" if key == Qt.Key_Left else "R"

    def paintEvent(self, event):
        if not self._background_pixmap.isNull():
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        painter.end()
        return super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_background()
        self._intro_video_widget.setGeometry(self.rect())
        self._position_intro_marker()
        self._position_final_marker()
        self._message_label.setGeometry(
            int(self.width() * 0.1),
            int(self.height() * 0.04),
            int(self.width() * 0.8),
            int(self.height() * 0.28),
        )
        if self._phase == "cross":
            self._show_centered_pixmap(self._cross_pixmap)
        elif self._phase == "intro_video":
            self._intro_video_widget.setGeometry(self.rect())
            self._intro_video_widget.show()
            self._intro_video_widget.raise_()
            self._position_intro_marker()
            self._intro_marker_label.show()
            self._intro_marker_label.raise_()
        elif self._phase == "welcome":
            self._show_fit_pixmap(self._welcome_pixmap)
        elif self._phase == "stimulus" and self._current_stimulus:
            self._show_centered_pixmap(QPixmap(self._current_stimulus))
        elif self._phase == "finished" and not self._final_pixmap.isNull():
            self._show_fit_pixmap(self._final_pixmap)
            self._position_final_marker()
            self._final_marker_label.show()
            self._final_marker_label.raise_()
