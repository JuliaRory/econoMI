import ast
import csv
import json
import os
import random
from datetime import datetime

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QFileDialog, QFrame, QLabel, QMessageBox, QSizePolicy, QWidget, QVBoxLayout

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
    resultsFileLoaded = pyqtSignal(list, str)
    sequenceSummaryReady = pyqtSignal(str)
    batLaunchRequested = pyqtSignal(str)

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
        self._update_timing_widgets()
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
        self.check_box_activate_bat = create_check_box(record.activate_bat, "Запускать bat", parent=self)
        self.line_edit_bat_file = create_lineedit(record.bat_file, parent=self, w=240)
        self.button_browse_bat = create_button("...", parent=self, w=36)
        self.button_launch_bat = create_button("Запустить", parent=self, w=90)

        self.combo_box_stimulus_type = QComboBox(self)
        self.combo_box_stimulus_type.addItems(stimuli.stimulus_types)
        self.combo_box_stimulus_type.setCurrentIndex(stimuli.stimulus_type_curr)

        self.combo_box_hljt_bundle = QComboBox(self)
        self.combo_box_hljt_bundle.setMinimumWidth(120)
        self._populate_bundle_combo(
            self.combo_box_hljt_bundle,
            stimuli.hands_stimuli_folder,
            getattr(stimuli, "hands_bundle", ""),
        )

        self.combo_box_mental_rotation_bundle = QComboBox(self)
        self.combo_box_mental_rotation_bundle.setMinimumWidth(120)
        self._populate_bundle_combo(
            self.combo_box_mental_rotation_bundle,
            stimuli.figures_stimuli_folder,
            getattr(stimuli, "figures_bundle", ""),
        )
        self.check_box_all_stimuli = create_check_box(getattr(stimuli, "use_all_stimuli", True), "Все стимулы", parent=self)
        self.spin_box_stimulus_count = create_spin_box(1, 10000, getattr(stimuli, "stimulus_count", 1), parent=self, w=80)

        self.spin_box_isi = create_spin_box(0.1, 30.0, stimuli.isi_s, parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.check_box_isi_range = create_check_box(stimuli.isi_range_enabled, "Диапазон", parent=self)
        self.spin_box_isi_min = create_spin_box(0.1, 30.0, stimuli.isi_min_s, parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.spin_box_isi_max = create_spin_box(0.1, 30.0, stimuli.isi_max_s, parent=self, data_type="float", step=0.1, decimals=1, w=80)
        blank_s = float(getattr(stimuli, "blank_s", getattr(stimuli, "blank_ms", 500) / 1000.0))
        self.spin_box_blank = create_spin_box(0.1, 30.0, blank_s, parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.check_box_blank_range = create_check_box(getattr(stimuli, "blank_range_enabled", False), "Диапазон", parent=self)
        self.spin_box_blank_min = create_spin_box(0.1, 30.0, getattr(stimuli, "blank_min_s", blank_s), parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.spin_box_blank_max = create_spin_box(0.1, 30.0, getattr(stimuli, "blank_max_s", blank_s), parent=self, data_type="float", step=0.1, decimals=1, w=80)
        self.spin_box_stimulus_ms = create_spin_box(100, 10000, stimuli.stimulus_ms, parent=self, step=100, w=90)
        self.spin_box_monitor = create_spin_box(1, 4, stimuli.monitor, parent=self, w=60)

        self.button_open = create_button("Открыть окно", parent=self, w=120)
        self.button_play = create_button(PLAY_LABEL, parent=self, disabled=True, w=48)
        self.button_stop = create_button("Стоп", parent=self, disabled=True, w=80)
        self.button_show_result = create_button("Показать результат", parent=self, disabled=True, w=160)

    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.label_title)
        layout.addWidget(self.label_status)
        layout.addWidget(self._create_record_block())
        layout.addWidget(self._create_stimuli_settings_block())
        layout.addWidget(self._create_settings_block())
        layout.addLayout(create_hbox([self.button_open, self.button_play, self.button_stop], stretch=False))
        layout.addWidget(self.button_show_result)
        layout.addWidget(self.label_stimuli_count)
        layout.addStretch()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _create_record_block(self):
        frame, layout = self._create_block_frame("Испытуемый и запись")
        layout.addLayout(create_hbox([QLabel("Испытуемый:", frame), self.line_edit_subject]))
        layout.addLayout(create_hbox([QLabel("Запись:", frame), self.line_edit_record]))
        layout.addWidget(self.check_box_save)
        layout.addWidget(self.check_box_activate_bat)
        layout.addLayout(create_hbox([QLabel("bat_file:", frame), self.line_edit_bat_file, self.button_browse_bat, self.button_launch_bat]))
        return frame

    def _create_stimuli_settings_block(self):
        frame, layout = self._create_block_frame("Настройки стимулов")
        layout.addLayout(create_hbox([QLabel("Тип стимулов:", frame), self.combo_box_stimulus_type]))
        layout.addLayout(create_hbox([QLabel("HLJT:", frame), self.combo_box_hljt_bundle]))
        layout.addLayout(create_hbox([QLabel("MentalRotation:", frame), self.combo_box_mental_rotation_bundle]))
        layout.addLayout(create_hbox([QLabel("Количество:", frame), self.spin_box_stimulus_count, self.check_box_all_stimuli]))
        return frame

    def _create_block_frame(self, title_text):
        frame = QFrame(self)
        frame.setObjectName("settingsBlock")
        frame.setStyleSheet(
            "QFrame#settingsBlock { background: #f7f8f7; border: 1px solid #d8d8d2; border-radius: 6px; }"
            "QLabel#settingsBlockTitle { font-weight: 600; }"
            "QLabel#settingsSection { color: #5d6760; font-weight: 600; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(title_text, frame)
        title.setObjectName("settingsBlockTitle")
        layout.addWidget(title)
        return frame, layout

    def _create_settings_block(self):
        frame, layout = self._create_block_frame("Параметры предъявления")
        layout.addLayout(create_hbox([QLabel("Монитор:", frame), self.spin_box_monitor]))
        layout.addLayout(create_hbox([self._section_label("Предъявление креста", frame)]))
        layout.addLayout(create_hbox([QLabel("Фикс., c:", frame), self.spin_box_isi, self.check_box_isi_range]))
        layout.addLayout(create_hbox([QLabel("min:", frame), self.spin_box_isi_min, QLabel("max:", frame), self.spin_box_isi_max]))
        layout.addLayout(create_hbox([self._section_label("Предъявление пустого экрана", frame)]))
        layout.addLayout(create_hbox([QLabel("Фикс., c:", frame), self.spin_box_blank, self.check_box_blank_range]))
        layout.addLayout(create_hbox([QLabel("min:", frame), self.spin_box_blank_min, QLabel("max:", frame), self.spin_box_blank_max]))
        layout.addLayout(create_hbox([self._section_label("Предъявление стимула", frame)]))
        layout.addLayout(create_hbox([QLabel("Фикс., мс:", frame), self.spin_box_stimulus_ms]))
        return frame

    def _section_label(self, text, parent):
        label = QLabel(text, parent)
        label.setObjectName("settingsSection")
        return label

    def _setup_connections(self):
        self.button_open.clicked.connect(self._on_open_button_click)
        self.button_play.clicked.connect(self._on_play_button_click)
        self.button_stop.clicked.connect(self._on_stop_button_click)
        self.button_show_result.clicked.connect(self._on_show_result_button_click)
        self.button_browse_bat.clicked.connect(self._on_browse_bat_file)
        self.button_launch_bat.clicked.connect(self._on_launch_bat_button_click)
        self.combo_box_stimulus_type.currentTextChanged.connect(self._on_stimulus_type_changed)
        self.combo_box_hljt_bundle.currentTextChanged.connect(self._on_bundle_changed)
        self.combo_box_mental_rotation_bundle.currentTextChanged.connect(self._on_bundle_changed)
        self.check_box_all_stimuli.stateChanged.connect(self._on_stimulus_count_changed)
        self.spin_box_stimulus_count.valueChanged.connect(self._on_stimulus_count_changed)
        self.spin_box_isi.valueChanged.connect(self._sync_settings_from_ui)
        self.check_box_isi_range.stateChanged.connect(self._sync_settings_from_ui)
        self.spin_box_isi_min.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_isi_max.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_blank.valueChanged.connect(self._sync_settings_from_ui)
        self.check_box_blank_range.stateChanged.connect(self._sync_settings_from_ui)
        self.spin_box_blank_min.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_blank_max.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_stimulus_ms.valueChanged.connect(self._sync_settings_from_ui)
        self.spin_box_monitor.valueChanged.connect(self._sync_settings_from_ui)
        self.line_edit_subject.textChanged.connect(self._on_record_identity_changed)
        self.line_edit_record.textChanged.connect(self._on_record_identity_changed)
        self.check_box_save.stateChanged.connect(self._sync_settings_from_ui)
        self.check_box_activate_bat.stateChanged.connect(self._sync_settings_from_ui)
        self.line_edit_bat_file.textChanged.connect(self._sync_settings_from_ui)

    def _sync_settings_from_ui(self, *_args):
        if self._is_arrows_stimulus_type() and self.check_box_all_stimuli.isChecked():
            self.check_box_all_stimuli.blockSignals(True)
            self.check_box_all_stimuli.setChecked(False)
            self.check_box_all_stimuli.blockSignals(False)

        self.settings.record.subject = self.line_edit_subject.text().strip()
        self.settings.record.record_name = self.line_edit_record.text().strip()
        self.settings.record.save_hdf = self.check_box_save.isChecked()
        self.settings.record.activate_bat = self.check_box_activate_bat.isChecked()
        self.settings.record.bat_file = self.line_edit_bat_file.text().strip()

        self.settings.stimuli.stimulus_type_curr = self.combo_box_stimulus_type.currentIndex()
        self.settings.stimuli.stimulus_type = self.combo_box_stimulus_type.currentText()
        self.settings.stimuli.stimuli_folder = self._current_stimuli_folder()
        self.settings.stimuli.hands_bundle = self.combo_box_hljt_bundle.currentText()
        self.settings.stimuli.figures_bundle = self.combo_box_mental_rotation_bundle.currentText()
        self.settings.stimuli.use_all_stimuli = self.check_box_all_stimuli.isChecked()
        self.settings.stimuli.stimulus_count = int(self.spin_box_stimulus_count.value())
        self.settings.stimuli.isi_s = float(self.spin_box_isi.value())
        self.settings.stimuli.isi_range_enabled = self.check_box_isi_range.isChecked()

        self.settings.stimuli.isi_min_s, self.settings.stimuli.isi_max_s = self._ordered_range_values(
            self.spin_box_isi_min,
            self.spin_box_isi_max,
        )
        self.settings.stimuli.blank_s = float(self.spin_box_blank.value())
        self.settings.stimuli.blank_range_enabled = self.check_box_blank_range.isChecked()
        self.settings.stimuli.blank_min_s, self.settings.stimuli.blank_max_s = self._ordered_range_values(
            self.spin_box_blank_min,
            self.spin_box_blank_max,
        )
        self.settings.stimuli.blank_ms = int(round(self.settings.stimuli.blank_s * 1000))
        self.settings.stimuli.stimulus_ms = int(self.spin_box_stimulus_ms.value())
        self.settings.stimuli.monitor = int(self.spin_box_monitor.value())
        self._update_timing_widgets()
        self._update_stimulus_count_widgets()

    def _update_timing_widgets(self):
        cross_range_enabled = self.check_box_isi_range.isChecked()
        self.spin_box_isi.setEnabled(not cross_range_enabled)
        self.spin_box_isi_min.setEnabled(cross_range_enabled)
        self.spin_box_isi_max.setEnabled(cross_range_enabled)

        blank_range_enabled = self.check_box_blank_range.isChecked()
        self.spin_box_blank.setEnabled(not blank_range_enabled)
        self.spin_box_blank_min.setEnabled(blank_range_enabled)
        self.spin_box_blank_max.setEnabled(blank_range_enabled)

    def _update_stimulus_count_widgets(self):
        is_arrows = self._is_arrows_stimulus_type()
        self.check_box_all_stimuli.setEnabled(not is_arrows)
        self.spin_box_stimulus_count.setEnabled(is_arrows or not self.check_box_all_stimuli.isChecked())

    @staticmethod
    def _ordered_range_values(min_widget, max_widget):
        min_s = float(min_widget.value())
        max_s = float(max_widget.value())
        if max_s < min_s:
            min_s, max_s = max_s, min_s
            min_widget.blockSignals(True)
            max_widget.blockSignals(True)
            min_widget.setValue(min_s)
            max_widget.setValue(max_s)
            min_widget.blockSignals(False)
            max_widget.blockSignals(False)
        return min_s, max_s

    def _on_stimulus_type_changed(self, _text):
        self._sync_settings_from_ui()
        self._update_stimuli_count()

    def _on_bundle_changed(self, _text):
        self._sync_settings_from_ui()
        self._update_stimuli_count()

    def _on_stimulus_count_changed(self, *_args):
        self._sync_settings_from_ui()
        self._update_stimuli_count()

    def _on_browse_bat_file(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Выберите bat-файл",
            os.path.dirname(self.line_edit_bat_file.text()) or os.getcwd(),
            "Batch files (*.bat);;All files (*)",
        )
        if not path:
            return
        self.line_edit_bat_file.setText(path)
        self._sync_settings_from_ui()

    def _on_launch_bat_button_click(self):
        self._sync_settings_from_ui()
        path = self.settings.record.bat_file
        if not path:
            QMessageBox.warning(self, "bat_file", "Выберите bat-файл.")
            return
        self.batLaunchRequested.emit(path)

    def _on_record_identity_changed(self, *_args):
        self._sync_settings_from_ui()
        self.load_existing_results_if_available()

    def load_existing_results_if_available(self):
        csv_path = self._record_path("_responses.csv", create_folder=False)
        if not os.path.isfile(csv_path):
            self.resultsFileLoaded.emit([], "")
            return
        try:
            with open(csv_path, "r", newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
        except OSError as exc:
            QMessageBox.warning(self, "Результаты", f"Не удалось открыть файл результатов:\n{csv_path}\n\n{exc}")
            return
        self._last_results = rows
        self.resultsFileLoaded.emit(rows, csv_path)

    def _bundle_names(self, folder):
        if not os.path.isdir(folder):
            return []
        return sorted(
            name
            for name in os.listdir(folder)
            if os.path.isdir(os.path.join(folder, name))
        )

    def _populate_bundle_combo(self, combo_box, folder, selected_name):
        names = self._bundle_names(folder)
        combo_box.addItems(names)
        if selected_name in names:
            combo_box.setCurrentText(selected_name)
        elif names:
            combo_box.setCurrentIndex(0)

    def _current_bundle_base_folder(self):
        if self.combo_box_stimulus_type.currentIndex() == 1:
            return self.settings.stimuli.figures_stimuli_folder
        return self.settings.stimuli.hands_stimuli_folder

    def _is_arrows_stimulus_type(self):
        return self.combo_box_stimulus_type.currentIndex() == 2

    def _current_bundle_name(self):
        if self.combo_box_stimulus_type.currentIndex() == 1:
            return self.combo_box_mental_rotation_bundle.currentText()
        return self.combo_box_hljt_bundle.currentText()

    def _current_stimuli_folder(self):
        if self._is_arrows_stimulus_type():
            return self.settings.stimuli.arrows_stimuli_folder
        bundle_name = self._current_bundle_name()
        if not bundle_name:
            return ""
        return os.path.join(self._current_bundle_base_folder(), bundle_name)

    def _current_order_file(self):
        bundle_name = self._current_bundle_name()
        if not bundle_name:
            return ""
        return os.path.join(self._current_bundle_base_folder(), f"{bundle_name}_order.txt")

    def _ordered_stimulus_names(self, order_file):
        if not os.path.isfile(order_file):
            return []
        with open(order_file, "r", encoding="utf-8") as file:
            text = file.read().strip()
        if not text:
            return []
        try:
            source = text if text.startswith("[") else f"[{text}]"
            items = ast.literal_eval(source)
        except (SyntaxError, ValueError):
            items = [
                line.strip().strip(",").strip("'\"")
                for line in text.splitlines()
                if line.strip()
            ]
        if isinstance(items, str):
            items = [items]
        return [os.path.basename(str(item).strip()) for item in items if str(item).strip()]

    def _stimuli_files(self):
        if self._is_arrows_stimulus_type():
            return self._balanced_arrows_stimuli_files()

        folder = self._current_stimuli_folder()
        if not os.path.isdir(folder):
            return []
        order_file = self._current_order_file()
        if not os.path.isfile(order_file):
            return []
        extensions = {ext.lower() for ext in self.settings.stimuli.extensions}
        files = [
            path
            for filename in self._ordered_stimulus_names(order_file)
            for path in [os.path.join(folder, filename)]
            if os.path.splitext(filename)[1].lower() in extensions and os.path.isfile(path)
        ]
        if self.check_box_all_stimuli.isChecked():
            return files
        return files[: int(self.spin_box_stimulus_count.value())]

    def _balanced_arrows_stimuli_files(self):
        folder = self.settings.stimuli.arrows_stimuli_folder
        if not os.path.isdir(folder):
            return []
        extensions = {ext.lower() for ext in self.settings.stimuli.extensions}
        files = [
            os.path.join(folder, filename)
            for filename in sorted(os.listdir(folder))
            if os.path.splitext(filename)[1].lower() in extensions
            and os.path.isfile(os.path.join(folder, filename))
        ]
        if not files:
            return []

        count = int(self.spin_box_stimulus_count.value())
        if len(files) == 1:
            return files * count

        left = count // 2
        right = count // 2
        if count % 2:
            if random.choice([True, False]):
                left += 1
            else:
                right += 1

        sequence = [files[0]] * left + [files[1]] * right
        random.shuffle(sequence)
        return sequence

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
        self.button_show_result.setEnabled(False)
        self.label_status.setText("Окно стимулов открыто")

    def _on_play_button_click(self):
        player = getattr(self, "_player_window", None)
        if isinstance(player, QWidget) and not player.isHidden():
            if not player.is_started:
                self._sync_settings_from_ui()
                files = self._stimuli_files()
                if not files:
                    QMessageBox.warning(self, "Стимулы", f"Нет изображений в папке:\n{self.settings.stimuli.stimuli_folder}")
                    return
                player.set_stimuli_files(files)
                if not self._confirm_save_targets_available():
                    return
            player.start_or_pause()
            self._update_play_label()

    def _on_stop_button_click(self):
        player = getattr(self, "_player_window", None)
        if isinstance(player, QWidget):
            player.finish()

    def _on_stimuli_started(self):
        self._last_results = []
        self.button_show_result.setEnabled(False)
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

        self.button_show_result.setEnabled(bool(self._last_results))
        text = f"Стимульный ряд завершён: {self._results_summary()}"
        self.label_status.setText(text)
        self.sequenceSummaryReady.emit(text)

    def _on_show_result_button_click(self):
        player = getattr(self, "_player_window", None)
        if not isinstance(player, QWidget) or player.isHidden():
            QMessageBox.warning(self, "Результат", "Окно стимулов закрыто.")
            return
        player.show_result_percentage(self._result_percentage())

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

    def _record_folder_path(self):
        subject = self.line_edit_subject.text().strip() or "subject"
        return os.path.abspath(os.path.join(self.settings.record.records_folder, subject))

    def _record_base_name(self):
        name = self.line_edit_record.text().strip() or "record"
        return "".join(char if char not in r'\/:*?"<>|' else "_" for char in name)

    def _record_path(self, extension, create_folder=True):
        folder = self._record_folder() if create_folder else self._record_folder_path()
        base = self._record_base_name()
        return os.path.join(folder, base + extension)

    def _save_target_paths(self):
        if not self.check_box_save.isChecked():
            return []
        return [
            self._record_path(".hdf5"),
            self._record_path("_responses.csv"),
        ]

    def _confirm_save_targets_available(self):
        existing_paths = [path for path in self._save_target_paths() if os.path.exists(path)]
        if not existing_paths:
            return True
        paths_text = "\n".join(existing_paths)
        QMessageBox.warning(
            self,
            "Сохранение",
            "Файл с таким названием уже существует. Сохранение в существующий файл не выполнено.\n\n"
            f"{paths_text}\n\nВведите другое название записи.",
        )
        return False

    def _start_nvx(self):
        hdf_path = self._record_path(".hdf5")
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
        csv_path = self._record_path("_responses.csv")
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

    def _result_percentage(self):
        total = len(self._last_results)
        if total == 0:
            return 0.0
        correct = sum(1 for item in self._last_results if self._is_correct_result(item))
        return correct * 100.0 / total

    def _results_summary(self):
        total = len(self._last_results)
        if total == 0:
            return "0% (0/0)"
        correct = sum(1 for item in self._last_results if self._is_correct_result(item))
        percent = correct * 100.0 / total
        return f"{percent:.0f}% ({correct}/{total})"

    @staticmethod
    def _is_correct_result(item):
        value = item.get("is_correct")
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "да"}
        return bool(value)

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
