"""Dialog for choosing the fixed data-x step to resample a curve onto."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_STEP = 1.0
_MIN_STEP = 1e-6
_MAX_STEP = 1e9


class ResampleDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resample to Fixed X Step")

        self.step_spinbox = QDoubleSpinBox()
        self.step_spinbox.setDecimals(6)
        self.step_spinbox.setRange(_MIN_STEP, _MAX_STEP)
        self.step_spinbox.setSingleStep(0.1)
        self.step_spinbox.setValue(_DEFAULT_STEP)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("X step size:"))
        layout.addWidget(self.step_spinbox)
        layout.addWidget(buttons)

    @property
    def step(self) -> float:
        return float(self.step_spinbox.value())
