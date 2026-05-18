from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout


def create_hbox(widgets, spacing=8, margins=(0, 0, 0, 0), stretch=True):
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    for widget in widgets:
        layout.addWidget(widget)
    layout.setAlignment(Qt.AlignLeft)
    if stretch:
        layout.addStretch()
    return layout


def create_vbox(widgets, spacing=8, margins=(0, 0, 0, 0)):
    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    for widget in widgets:
        layout.addWidget(widget)
    return layout
