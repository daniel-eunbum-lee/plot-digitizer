"""Dialog for reviewing a sampled curve color and match tolerance before auto-tracing."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_TOLERANCE = 30


class ColorPickerDialog(QDialog):
    def __init__(self, bgr: tuple[int, int, int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto-Trace Curve by Color")

        blue, green, red = bgr
        swatch = QLabel(f"Sampled color: RGB({red}, {green}, {blue})")
        swatch.setStyleSheet(f"background-color: rgb({red},{green},{blue}); padding: 8px;")

        self.tolerance_spinbox = QSpinBox()
        self.tolerance_spinbox.setRange(0, 255)
        self.tolerance_spinbox.setValue(_DEFAULT_TOLERANCE)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(swatch)
        layout.addWidget(QLabel("Color match tolerance:"))
        layout.addWidget(self.tolerance_spinbox)
        layout.addWidget(buttons)

    @property
    def tolerance(self) -> int:
        return self.tolerance_spinbox.value()
