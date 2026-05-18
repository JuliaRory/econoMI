import os
import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

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
        self._launch_qml_control_if_needed()
        self._setup_ui()
        self._setup_layout()
        self.resize(980, 540)

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

        self._current_stimulus_label = QLabel("Стимул: --", self._status_panel)
        self._summary_label = QLabel("Правильных ответов: --", self._status_panel)

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
        self._stimuli_panel.sequenceSummaryReady.connect(self._on_sequence_summary_ready)

    def _setup_layout(self):
        status_layout = QVBoxLayout(self._status_panel)
        status_layout.setContentsMargins(14, 14, 14, 14)
        status_layout.setSpacing(10)
        status_layout.addWidget(self._status_label)
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
        bat_path = os.path.abspath(record.bat_file)
        if not os.path.exists(bat_path):
            print(f"QML control bat not found: {bat_path}")
            return
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([bat_path], cwd=os.path.dirname(bat_path), creationflags=creationflags)
        except Exception as exc:
            print(f"Could not launch QML control: {exc}")

    def _on_recording_started(self, hdf_path):
        self._status_label.setText(f"NVX: запись\nHDF: {hdf_path}")

    def _on_recording_finished(self):
        self._status_label.setText("NVX: остановлено")

    def _on_presentation_started(self):
        self._answers_table.setRowCount(0)
        self._current_stimulus_label.setText("Стимул: --")
        self._summary_label.setText("Правильных ответов: --")

    def _on_current_stimulus_changed(self, stimulus_name):
        self._current_stimulus_label.setText(f"Стимул: {stimulus_name}")

    def _on_trial_result_ready(self, result):
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

    def _on_sequence_summary_ready(self, text):
        self._summary_label.setText(text)

    def closeEvent(self, event):
        try:
            service = self.resonance.getService("Resonance-control")
            service.sendTransition("!terminate")
        except Exception:
            pass
        event.accept()
