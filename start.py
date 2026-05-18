import os
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from settings.settings import AppSettings
from ui.main_window import MainWindow
from utils.resonance_control import ResonanceAppProxy


class OfflineDriver:
    def outputMessageStream(self, name):
        def send(message):
            print(f"[offline:{name}] {message}")

        return send

    def pollEvents(self):
        return None


def _create_driver(app_name):
    try:
        from drivers.resonance_foreign_driver import Driver

        return Driver(app_name)
    except Exception as exc:
        print(f"Resonance driver is not available, starting offline UI: {exc}")
        return OfflineDriver()


if __name__ == "__main__":
    os.environ.setdefault(
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        os.path.abspath(r"venv\Lib\site-packages\PyQt5\Qt5\plugins"),
    )

    app = QApplication(sys.argv)
    qss_path = os.path.join("styles", "theme.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as file:
            app.setStyleSheet(file.read())

    settings = AppSettings()
    driver = _create_driver(settings.app_service_name)
    control_stream = driver.outputMessageStream("controlSignal")
    stimuli_stream = driver.outputMessageStream("stimuli")
    responses_stream = driver.outputMessageStream("responses")
    resonance = ResonanceAppProxy(control_stream)

    poll_timer = QTimer()
    poll_timer.timeout.connect(driver.pollEvents)
    poll_timer.start(20)

    window = MainWindow(resonance, stimuli_stream, responses_stream, settings=settings)
    window.show()
    sys.exit(app.exec_())
