import os
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from settings.settings import AppSettings
from ui.stimuli_control_panel import StimuliControlPanel


class MainWindow(QWidget):
    def __init__(self, resonance, stimuli_stream, responses_stream, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings or AppSettings()
        self.resonance = resonance
        self._stimuli_stream = stimuli_stream
        self._responses_stream = responses_stream

        self.setWindowTitle("econoMI UI")
        self._set_window_icon()
        self._launch_qml_control_if_needed()
        self._setup_ui()
        self._setup_layout()
        self.resize(980, 540)

    def _set_window_icon(self):
        icon_path = os.path.abspath(os.path.join("resources", "icon_hand.png"))
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _setup_ui(self):
        self._stimuli_panel = StimuliControlPanel(
            self.settings,
            self.resonance,
            self._stimuli_stream,
            self._responses_stream,
            parent=self,
        )

        self._status_panel = QWidget(self)
        self._status_panel.setObjectName("panel")
        self._status_label = QLabel("NVX: ожидание", self._status_panel)
        self._status_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._recording_indicator_label = QLabel("•Rec", self._status_panel)
        self._recording_indicator_label.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self._recording_indicator_label.setStyleSheet("color: #d00000; font-weight: 700; font-size: 14pt;")
        self._recording_indicator_label.hide()

        self._current_stimulus_label = QLabel("Стимул: --", self._status_panel)
        self._summary_label = QLabel("Результат: --", self._status_panel)

        self._answers_table = QTableWidget(0, 4, self._status_panel)
        self._answers_table.setHorizontalHeaderLabels(["#", "Стимул", "Ответ", "RT, мс"])
        self._answers_table.verticalHeader().setVisible(False)
        self._answers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._answers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._answers_table.horizontalHeader().setStretchLastSection(True)

        self._stimuli_panel.presentationStarted.connect(self._on_presentation_started)
        self._stimuli_panel.recordingStarted.connect(self._on_recording_started)
        self._stimuli_panel.recordingFinished.connect(self._on_recording_finished)
        self._stimuli_panel.currentStimulusChanged.connect(self._on_current_stimulus_changed)
        self._stimuli_panel.trialResultReady.connect(self._on_trial_result_ready)
        self._stimuli_panel.resultsFileLoaded.connect(self._on_results_file_loaded)
        self._stimuli_panel.sequenceSummaryReady.connect(self._on_sequence_summary_ready)
        self._stimuli_panel.batLaunchRequested.connect(self._on_bat_launch_requested)
        self._stimuli_panel.load_existing_results_if_available()

    def _setup_layout(self):
        status_header_layout = QHBoxLayout()
        status_header_layout.setContentsMargins(0, 0, 0, 0)
        status_header_layout.addWidget(self._status_label, 1)
        status_header_layout.addWidget(self._recording_indicator_label, 0, Qt.AlignTop | Qt.AlignRight)

        status_layout = QVBoxLayout(self._status_panel)
        status_layout.setContentsMargins(14, 14, 14, 14)
        status_layout.setSpacing(10)
        status_layout.addLayout(status_header_layout)
        status_layout.addWidget(self._current_stimulus_label)
        status_layout.addWidget(self._summary_label)
        status_layout.addWidget(self._answers_table)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._stimuli_panel)
        splitter.addWidget(self._status_panel)
        splitter.setSizes([420, 560])
        splitter.setCollapsible(0, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(splitter)

    def _launch_qml_control_if_needed(self):
        record = self.settings.record
        if not record.activate_bat:
            return
        self._launch_bat_file(record.bat_file, warn=False)

    def _launch_bat_file(self, path, warn=True):
        bat_path = self._app_path(path)
        if not os.path.exists(bat_path):
            message = f"QML control bat not found: {bat_path}"
            if warn:
                QMessageBox.warning(self, "bat_file", message)
            else:
                print(message)
            return
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([bat_path], cwd=os.path.dirname(bat_path), creationflags=creationflags)
        except Exception as exc:
            message = f"Could not launch QML control: {exc}"
            if warn:
                QMessageBox.warning(self, "bat_file", message)
            else:
                print(message)

    def _on_bat_launch_requested(self, path):
        self._launch_bat_file(path, warn=True)

    @staticmethod
    def _app_path(path):
        if os.path.isabs(path):
            return path
        base_dir = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        return os.path.abspath(os.path.join(base_dir, path))

    def _on_recording_started(self, hdf_path):
        self._status_label.setText(f"NVX: запись\nHDF: {hdf_path}")
        self._recording_indicator_label.show()

    def _on_recording_finished(self):
        self._status_label.setText("NVX: остановлено")
        self._recording_indicator_label.hide()

    def _on_presentation_started(self):
        self._answers_table.setRowCount(0)
        self._current_stimulus_label.setText("Стимул: --")
        self._summary_label.setText("Результат: --")

    def _on_current_stimulus_changed(self, stimulus_name):
        self._current_stimulus_label.setText(f"Стимул: {stimulus_name}")

    def _on_trial_result_ready(self, result):
        self._append_result_row(result)

    def _append_result_row(self, result):
        row = self._answers_table.rowCount()
        self._answers_table.insertRow(row)
        values = [
            result.get("trial_index", ""),
            result.get("stimulus", ""),
            result.get("response") or "",
            "" if result.get("rt_ms") is None else result.get("rt_ms"),
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if column in (0, 2, 3):
                item.setTextAlignment(Qt.AlignCenter)
            self._answers_table.setItem(row, column, item)
        self._answers_table.scrollToBottom()

    def _on_results_file_loaded(self, rows, csv_path):
        self._answers_table.setRowCount(0)
        for result in rows:
            self._append_result_row(result)
        if csv_path:
            self._summary_label.setText(f"Загружены результаты. Правильно: {self._results_summary(rows)}\n{csv_path}")
        else:
            self._summary_label.setText("Результат: --")

    def _on_sequence_summary_ready(self, text):
        self._summary_label.setText(text)

    def _results_summary(self, rows):
        total = len(rows)
        if total == 0:
            return "0% (0/0)"
        correct = sum(1 for row in rows if self._is_correct_result(row))
        percent = correct * 100.0 / total
        return f"{percent:.0f}% ({correct}/{total})"

    @staticmethod
    def _is_correct_result(row):
        value = row.get("is_correct")
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "да"}
        return bool(value)

    def closeEvent(self, event):
        try:
            service = self.resonance.getService("Resonance-control")
            service.sendTransition("!terminate")
        except Exception:
            pass
        event.accept()
