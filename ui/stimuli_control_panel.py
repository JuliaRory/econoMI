import csv
import json
import os
from datetime import datetime

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QFrame, QLabel, QMessageBox, QSizePolicy, QWidget, QVBoxLayout

from settings.settings import AppSettings
from ui.video_player import HandStimuliPresentation
from utils.layout_utils import create_hbox
from utils.ui_helpers import create_button, create_check_box, create_lineedit, create_spin_box


PLAY_LABEL = "▶"
PAUSE_LABEL = "⏸"


class StimuliControlPanel(QFrame):
    presentationStarted = pyqtSignal()
    recordingStarted = pyqtSignal(str)
    recordingFinished = pyqtSignal()
    currentStimulusChanged = pyqtSignal(str)
    trialResultReady = pyqtSignal(dict)
    sequenceSummaryReady = pyqtSignal(str)

    def __init__(self, settings: AppSettings, resonance, stimuli_stream, responses_stream, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.settings = settings
        self.resonance = resonance
        self.stimuli_stream = stimuli_stream
        self.responses_stream = responses_stream
        self._service = self.resonance.getService(self.settings.record.service_name)
        self._player_window = None
        self._csv_file = None
        self._csv_writer = None
        self._recording = False
        self._last_hdf_path = ""
        self._last_results = []

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._update_isi_widgets()
        self._sync_settings_from_ui()
        self._update_stimuli_count()

    def _setup_ui(self):
        self.label_title = QLabel("econoMI", self)
        self.label_title.setObjectName("title")
        self.label_status = QLabel("Готово", self)
        self.label_status.setObjectName("status")
        self.label_stimuli_count = QLabel("", self)

        record = self.settings.record
        stimuli = self.settings.stimuli
        self.line_edit_subject = create_lineedit(record.subject, parent=self, w=140)
        self.line_edit_record = create_lineedit(record.record_name, parent=self, w=180)
        self.check_box_save = create_check_box(record.save_hdf, "Сохранять файл", parent=self)

        self.combo_box_stimulus_type = QComboBox(self)
        self.combo_box_stimulus_type.addItems(stimuli.stimulus_types)
        self.combo_box_stimulus_type.setCurrentIndex(stimuli.stimulus_type_curr)

        self.spin_box_isi = create_spin_box(0.1, 30.0, stimuli.isi_s, parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.check_box_isi_range = create_check_box(stimuli.isi_range_enabled, "Диапазон", parent=self)
        self.spin_box_isi_min = create_spin_box(0.1, 30.0, stimuli.isi_min_s, parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.spin_box_isi_max = create_spin_box(0.1, 30.0, stimuli.isi_max_s, parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.spin_box_stimulus_ms = create_spin_box(100, 10000, stimuli.stimulus_ms, parent=self, step=100, w=90)
        self.spin_box_monitor = create_spin_box(1, 4, stimuli.monitor, parent=self, w=60)

        self.button_open = create_button("Открыть окно", parent=self, w=120)
        self.button_play = create_button(PLAY_LABEL, parent=self, disabled=True, w=48)
        self.button_stop = create_button("Стоп", parent=self, disabled=True, w=80)

    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.label_title)
        layout.addWidget(self.label_status)
        layout.addLayout(create_hbox([QLabel("Испытуемый:", self), self.line_edit_subject]))
        layout.addLayout(create_hbox([QLabel("Запись:", self), self.line_edit_record]))
        layout.addLayout(create_hbox([QLabel("Тип стимулов:", self), self.combo_box_stimulus_type]))
        layout.addLayout(create_hbox([QLabel("ISI, c:", self), self.spin_box_isi, self.check_box_isi_range, QLabel("Монитор:", self), self.spin_box_monitor]))
        layout.addLayout(create_hbox([QLabel("ISI min:", self), self.spin_box_isi_min, QLabel("max:", self), self.spin_box_isi_max]))
        layout.addLayout(create_hbox([QLabel("Стимул, мс:", self), self.spin_box_stimulus_ms]))
        layout.addWidget(self.check_box_save)
        layout.addLayout(create_hbox([self.button_open, self.button_play, self.button_stop], stretch=False))
        layout.addWidget(self.label_stimuli_count)
        layout.addStretch()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _setup_connections(self):
        self.button_open.clicked.connect(self._on_open_button_click)
        self.button_play.clicked.connect(self._on_play_button_click)
        self.button_stop.clicked.connect(self._on_stop_button_click)
        self.combo_box_stimulus_type.currentTextChanged.connect(self._on_stimulus_type_changed)
        self.spin_box_isi.valueChanged.connect(self._sync_settings_from_ui)
        self.check_box_isi_range.stateChanged.connect(self._sync_settings_from_ui)
        self.spin_box_isi_min.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_isi_max.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_stimulus_ms.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_monitor.valueChanged.connect(self._sync_settings_from_ui)
        self.line_edit_subject.textChanged.connect(self._sync_settings_from_ui)
        self.line_edit_record.textChanged.connect(self._sync_settings_from_ui)
        self.check_box_save.stateChanged.connect(self._sync_settings_from_ui)

    def _sync_settings_from_ui(self, *_args):
        self.settings.record.subject = self.line_edit_subject.text().strip()
        self.settings.record.record_name = self.line_edit_record.text().strip()
        self.settings.record.save_hdf = self.check_box_save.isChecked()

        self.settings.stimuli.stimulus_type_curr = self.combo_box_stimulus_type.currentIndex()
        self.settings.stimuli.stimulus_type = self.combo_box_stimulus_type.currentText()
        self.settings.stimuli.stimuli_folder = self._current_stimuli_folder()
        self.settings.stimuli.isi_s = float(self.spin_box_isi.value())
        self.settings.stimuli.isi_range_enabled = self.check_box_isi_range.isChecked()

        min_s = float(self.spin_box_isi_min.value())
        max_s = float(self.spin_box_isi_max.value())
        if max_s < min_s:
            min_s, max_s = max_s, min_s
            self.spin_box_isi_min.blockSignals(True)
            self.spin_box_isi_max.blockSignals(True)
            self.spin_box_isi_min.setValue(min_s)
            self.spin_box_isi_max.setValue(max_s)
            self.spin_box_isi_min.blockSignals(False)
            self.spin_box_isi_max.blockSignals(False)

        self.settings.stimuli.isi_min_s = min_s
        self.settings.stimuli.isi_max_s = max_s
        self.settings.stimuli.stimulus_ms = int(self.spin_box_stimulus_ms.value())
        self.settings.stimuli.monitor = int(self.spin_box_monitor.value())
        self._update_isi_widgets()

    def _update_isi_widgets(self):
        range_enabled = self.check_box_isi_range.isChecked()
        self.spin_box_isi.setEnabled(not range_enabled)
        self.spin_box_isi_min.setEnabled(range_enabled)
        self.spin_box_isi_max.setEnabled(range_enabled)

    def _on_stimulus_type_changed(self, _text):
        self._sync_settings_from_ui()
        self._update_stimuli_count()

    def _current_stimuli_folder(self):
        if self.combo_box_stimulus_type.currentIndex() == 1:
            return self.settings.stimuli.figures_stimuli_folder
        return self.settings.stimuli.hands_stimuli_folder

    def _stimuli_files(self):
        folder = self._current_stimuli_folder()
        if not os.path.isdir(folder):
            return []
        extensions = {ext.lower() for ext in self.settings.stimuli.extensions}
        return [
            os.path.join(folder, filename)
            for filename in sorted(os.listdir(folder))
            if os.path.splitext(filename)[1].lower() in extensions
        ]

    def _update_stimuli_count(self):
        n = len(self._stimuli_files())
        self.label_stimuli_count.setText(f"Стимулов: {n}")

    def _on_open_button_click(self):
        player = getattr(self, "_player_window", None)
        if isinstance(player, QWidget) and not player.isHidden():
            player.finish()
            return

        self._sync_settings_from_ui()
        files = self._stimuli_files()
        if not files:
            QMessageBox.warning(self, "Стимулы", f"Нет изображений в папке:\n{self.settings.stimuli.stimuli_folder}")
            return

        self._player_window = HandStimuliPresentation(self.settings.stimuli, files)
        self._player_window.stimuliStarted.connect(self._on_stimuli_started)
        self._player_window.stimuliPaused.connect(self._on_stimuli_paused)
        self._player_window.stimuliFinished.connect(self._on_stimuli_finished)
        self._player_window.currIdxChanged.connect(self._on_trial_index_changed)
        self._player_window.stimulusShown.connect(self._on_stimulus_shown)
        self._player_window.trialFinished.connect(self._on_trial_finished)
        self._player_window.show()
        self._player_window.raise_()
        self._player_window.activateWindow()

        self.button_open.setText("Закрыть окно")
        self.button_play.setEnabled(True)
        self.button_stop.setEnabled(True)
        self.label_status.setText("Окно стимулов открыто")

    def _on_play_button_click(self):
        player = getattr(self, "_player_window", None)
        if isinstance(player, QWidget) and not player.isHidden():
            player.start_or_pause()
            self._update_play_label()

    def _on_stop_button_click(self):
        player = getattr(self, "_player_window", None)
        if isinstance(player, QWidget):
            player.finish()

    def _on_stimuli_started(self):
        self._last_results = []
        self.presentationStarted.emit()
        self._open_csv_if_needed()
        if self.check_box_save.isChecked():
            self._start_nvx()
        self.label_status.setText("Предъявление идёт")
        self.button_play.setText(PAUSE_LABEL)

    def _on_stimuli_paused(self):
        self._update_play_label()

    def _on_stimuli_finished(self):
        self._stop_nvx_if_needed()
        self._close_csv()
        self.button_open.setText("Открыть окно")
        self.button_play.setText(PLAY_LABEL)
        self.button_play.setEnabled(False)
        self.button_stop.setEnabled(False)

        player = getattr(self, "_player_window", None)
        if isinstance(player, QWidget):
            self._last_results = player.trial_results

        text = self._feedback_text()
        self.label_status.setText(text)
        self.sequenceSummaryReady.emit(text)

    def _on_trial_index_changed(self, idx):
        self.label_status.setText(f"Трайл #{idx}")

    def _on_stimulus_shown(self, path):
        stimulus_name = os.path.basename(path)
        self.currentStimulusChanged.emit(stimulus_name)
        self._send_message(self.stimuli_stream, {"stimulus": stimulus_name})

    def _on_trial_finished(self, result):
        self._last_results.append(result)
        self.trialResultReady.emit(result)
        self._send_message(self.responses_stream, self._response_stream_payload(result))
        if self._csv_writer is not None:
            self._csv_writer.writerow(result)
            self._csv_file.flush()

    @staticmethod
    def _response_stream_payload(result):
        return {
            "trial_index": result.get("trial_index"),
            "stimulus": result.get("stimulus"),
            "response": result.get("response"),
            "rt_ms": result.get("rt_ms"),
            "timestamp": result.get("timestamp"),
        }

    def _update_play_label(self):
        player = getattr(self, "_player_window", None)
        if not isinstance(player, QWidget):
            self.button_play.setText(PLAY_LABEL)
            return
        self.button_play.setText(PLAY_LABEL if player.is_paused else PAUSE_LABEL)

    def _record_folder(self):
        subject = self.line_edit_subject.text().strip() or "subject"
        folder = os.path.abspath(os.path.join(self.settings.record.records_folder, subject))
        os.makedirs(folder, exist_ok=True)
        return folder

    def _record_base_name(self):
        name = self.line_edit_record.text().strip() or "record"
        return "".join(char if char not in r'\/:*?"<>|' else "_" for char in name)

    def _unique_path(self, extension):
        folder = self._record_folder()
        base = self._record_base_name()
        path = os.path.join(folder, base + extension)
        if not os.path.exists(path):
            return path
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(folder, f"{base}_{stamp}{extension}")

    def _start_nvx(self):
        hdf_path = self._unique_path(".hdf5")
        self._last_hdf_path = hdf_path
        self._service.sendTransition(
            "start",
            stream=self.settings.record.stream_name,
            add_stimuli=True,
            filename=hdf_path,
            app_service_name=self.settings.app_service_name,
        )
        self._recording = True
        self.recordingStarted.emit(hdf_path)

    def _stop_nvx_if_needed(self):
        if not self._recording:
            return
        self._service.sendTransition("stop")
        self._recording = False
        self.recordingFinished.emit()

    def _open_csv_if_needed(self):
        if not self.check_box_save.isChecked():
            return
        csv_path = self._unique_path("_responses.csv")
        self._csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        fieldnames = [
            "trial_index",
            "stimulus",
            "correct_answer",
            "response",
            "rt_ms",
            "isi_ms",
            "is_correct",
            "timestamp",
        ]
        self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=fieldnames)
        self._csv_writer.writeheader()

    def _close_csv(self):
        if self._csv_file is not None:
            self._csv_file.close()
        self._csv_file = None
        self._csv_writer = None

    def _feedback_text(self):
        total = len(self._last_results)
        correct = sum(1 for item in self._last_results if item.get("is_correct"))
        return f"Правильных ответов: {correct}/{total}"

    @staticmethod
    def _send_message(stream, message):
        if stream is None:
            return
        payload = dict(message)
        payload.setdefault("timestamp", datetime.now().isoformat(timespec="milliseconds"))
        stream(json.dumps(payload, ensure_ascii=False))

    def closeEvent(self, event):
        self._stop_nvx_if_needed()
        self._close_csv()
        player = getattr(self, "_player_window", None)
        if isinstance(player, QWidget) and not player.isHidden():
            player.finish()
        event.accept()
