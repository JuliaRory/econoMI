import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QWidget


OPEN_EYES_MS = 60_000
CLOSED_EYES_MS = 60_000
MARKER_MS = 50


def resource_path(relative_path):
    base_dir = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_dir, relative_path)


class ClosedOpenEyesPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("econoMI closed/open eyes")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.BlankCursor)

        self._state = "idle"
        self._white_pixmap = QPixmap(resource_path(r"resources\base images\base_white_barred_lightGrey.png"))
        self._cross_pixmap = QPixmap(resource_path(r"resources\base images\base_cross_black_barred_lightGrey.png"))
        self._black_pixmap = QPixmap(resource_path(r"resources\base images\base_black_barred_lightGrey.png"))

        self._background_label = QLabel(self)
        self._background_label.setAlignment(Qt.AlignCenter)
        self._background_label.setStyleSheet("background: white;")

        self._message_label = QLabel("закройте глаза", self)
        self._message_label.setAlignment(Qt.AlignCenter)
        self._message_label.setStyleSheet("color: white; background: transparent;")
        font = QFont()
        font.setPointSize(56)
        font.setBold(True)
        self._message_label.setFont(font)
        self._message_label.hide()

        self._marker_label = QLabel(self)
        self._marker_label.setFixedSize(80, 80)
        self._marker_label.setStyleSheet("background: black;")
        self._marker_label.hide()

        self._phase_timer = QTimer(self)
        self._phase_timer.setSingleShot(True)
        self._phase_timer.timeout.connect(self._on_phase_timeout)

        self._marker_timer = QTimer(self)
        self._marker_timer.setSingleShot(True)
        self._marker_timer.timeout.connect(self._marker_label.hide)

        self._show_background(self._white_pixmap)

    def start_sequence(self):
        if self._state in {"open_eyes", "closed_eyes"}:
            return
        self._state = "open_eyes"
        self._message_label.hide()
        self._marker_label.hide()
        self._show_background(self._cross_pixmap)
        self._phase_timer.start(OPEN_EYES_MS)

    def _on_phase_timeout(self):
        if self._state == "open_eyes":
            self._start_closed_eyes_phase()
        elif self._state == "closed_eyes":
            self._finish_sequence()

    def _start_closed_eyes_phase(self):
        self._state = "closed_eyes"
        self._show_background(self._black_pixmap)
        self._message_label.show()
        self._message_label.raise_()
        self._position_marker()
        self._marker_label.show()
        self._marker_label.raise_()
        self._marker_timer.start(MARKER_MS)
        self._phase_timer.start(CLOSED_EYES_MS)

    def _finish_sequence(self):
        self._state = "finished"
        self._phase_timer.stop()
        self._marker_timer.stop()
        self._marker_label.hide()
        self._message_label.hide()
        self._show_background(self._white_pixmap)

    def _show_background(self, pixmap):
        self._current_pixmap = pixmap
        self._update_background()

    def _update_background(self):
        self._background_label.setGeometry(self.rect())
        if self._current_pixmap.isNull():
            self._background_label.clear()
            return
        scaled = self._current_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self._background_label.setPixmap(scaled)
        self._background_label.raise_()
        self._message_label.raise_()
        self._marker_label.raise_()

    def _position_marker(self):
        self._marker_label.move(self.width() - self._marker_label.width(), 0)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key_Space:
            self.start_sequence()
            return
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        if not getattr(self, "_current_pixmap", QPixmap()).isNull():
            return super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.end()
        return super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_background()
        self._message_label.setGeometry(self.rect())
        self._position_marker()

    def show_on_monitor(self, monitor_number=1):
        screens = QApplication.instance().screens()
        if not screens:
            raise RuntimeError("No Qt screens are available.")
        monitor_index = min(max(int(monitor_number) - 1, 0), len(screens) - 1)
        screen = screens[monitor_index]
        self.create()
        window = self.windowHandle()
        if window is not None:
            window.setScreen(screen)
        self.move(screen.geometry().topLeft())
        self.setGeometry(screen.geometry())
        self.showFullScreen()


def main():
    if not getattr(sys, "frozen", False):
        os.environ.setdefault(
            "QT_QPA_PLATFORM_PLUGIN_PATH",
            os.path.abspath(r"venv\Lib\site-packages\PyQt5\Qt5\plugins"),
        )

    app = QApplication(sys.argv)
    player = ClosedOpenEyesPlayer()
    player.show_on_monitor(2)
    player.activateWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
