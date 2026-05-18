from PyQt5.QtWidgets import QCheckBox, QDoubleSpinBox, QLineEdit, QPushButton, QSpinBox


def create_button(text, callback=None, disabled=False, parent=None, w=None):
    button = QPushButton(text, parent)
    button.setDisabled(disabled)
    if w is not None:
        button.setFixedWidth(w)
    if callback is not None:
        button.clicked.connect(callback)
    return button


def create_lineedit(text="", parent=None, w=None):
    lineedit = QLineEdit(parent)
    lineedit.setText(text)
    if w is not None:
        lineedit.setFixedWidth(w)
    return lineedit


def create_check_box(state, text="", parent=None):
    checkbox = QCheckBox(text, parent)
    checkbox.setChecked(bool(state))
    return checkbox


def create_spin_box(min_value, max_value, value, parent=None, data_type="int", step=1, decimals=1, w=None):
    if data_type == "float":
        spin_box = QDoubleSpinBox(parent)
        spin_box.setDecimals(decimals)
    else:
        spin_box = QSpinBox(parent)
    spin_box.setRange(min_value, max_value)
    spin_box.setSingleStep(step)
    spin_box.setValue(value)
    if w is not None:
        spin_box.setFixedWidth(w)
    return spin_box
