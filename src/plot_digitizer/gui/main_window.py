"""Main application window: menu shell, canvas, calibration, and point-picking wiring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QUndoStack
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QFileDialog,
    QGraphicsItem,
    QMainWindow,
    QMessageBox,
    QTableView,
)

from plot_digitizer.calibration.resample import resample_curve_to_step
from plot_digitizer.gui.calibration_dialog import AxisCalibrationDialog
from plot_digitizer.gui.canvas import ImageCanvas
from plot_digitizer.gui.color_picker_dialog import ColorPickerDialog
from plot_digitizer.gui.curve_panel import CurvePanel
from plot_digitizer.gui.modes import InteractionMode
from plot_digitizer.gui.overlays import (
    make_data_point_marker,
    make_horizontal_reference_line,
    make_vertical_reference_line,
)
from plot_digitizer.gui.point_table import PointTableModel
from plot_digitizer.gui.resample_dialog import ResampleDialog
from plot_digitizer.gui.undo_commands import AddPointCommand, ResampleCurveCommand
from plot_digitizer.imaging.color import sample_color_bgr
from plot_digitizer.imaging.curve_trace import trace_curve_by_color
from plot_digitizer.imaging.io import ImageLoadError, load_image
from plot_digitizer.imaging.perspective import PerspectiveTransform, estimate_output_size
from plot_digitizer.io_export.csv_export import export_curve_csv
from plot_digitizer.io_export.project_file import load_project, save_project
from plot_digitizer.model.curve import Curve
from plot_digitizer.model.point import Point
from plot_digitizer.model.project import Project

_IMAGE_FILE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
_X_REFERENCE_COLOR = QColor("red")
_Y_REFERENCE_COLOR = QColor("blue")
_DATA_POINT_COLOR = QColor("#1f77b4")
_PERSPECTIVE_POINT_COLOR = QColor("orange")
_DEFAULT_CURVE_NAME = "Curve 1"
_PERSPECTIVE_CORNER_COUNT = 4
_MIN_RESAMPLE_POINTS = 2


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Plot Digitizer")
        self.resize(1000, 700)

        self.canvas = ImageCanvas()
        self.canvas.imageClicked.connect(self._on_canvas_clicked)
        self.setCentralWidget(self.canvas)

        self.project: Project | None = None
        self._raw_image: np.ndarray | None = None
        self._working_image: np.ndarray | None = None
        self._calibration_dialog: AxisCalibrationDialog | None = None
        self._pending_calibration_axis: str | None = None
        self._calibration_overlay_items: list[QGraphicsItem] = []
        self._data_point_overlay_items: list[QGraphicsItem] = []
        self._perspective_pick_points: list[Point] = []
        self._perspective_overlay_items: list[QGraphicsItem] = []
        self._undo_stack = QUndoStack(self)

        self._point_table_model = PointTableModel()
        self._curve_panel = CurvePanel()
        self._curve_panel.curveSelected.connect(self._on_curve_selected)
        self._curve_panel.addCurveRequested.connect(self._on_add_curve_requested)
        self._curve_panel.deleteCurveRequested.connect(self._on_delete_curve_requested)
        self._curve_panel.resampleRequested.connect(self._on_resample_requested)
        self._build_point_table_dock()
        self._build_curve_panel_dock()
        self._build_menu()

    def _build_point_table_dock(self) -> None:
        table_view = QTableView()
        table_view.setModel(self._point_table_model)
        dock = QDockWidget("Digitized Points", self)
        dock.setWidget(table_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _build_curve_panel_dock(self) -> None:
        dock = QDockWidget("Curves", self)
        dock.setWidget(self._curve_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = file_menu.addAction("&Open Image...")
        open_action.triggered.connect(self.open_image_dialog)
        reset_action = file_menu.addAction("&Reset Project...")
        reset_action.triggered.connect(self.reset_project)
        open_project_action = file_menu.addAction("Open &Project...")
        open_project_action.triggered.connect(self.open_project_dialog)
        save_project_action = file_menu.addAction("&Save Project As...")
        save_project_action.triggered.connect(self.save_project_dialog)
        export_action = file_menu.addAction("&Export Points to CSV...")
        export_action.triggered.connect(self.export_csv_dialog)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self._undo_stack.createUndoAction(self, "Undo"))
        edit_menu.addAction(self._undo_stack.createRedoAction(self, "Redo"))

        calibration_menu = self.menuBar().addMenu("&Calibration")
        calibrate_action = calibration_menu.addAction("&Axes...")
        calibrate_action.triggered.connect(self.open_calibration_dialog)

        points_menu = self.menuBar().addMenu("&Points")
        self._pick_points_action = QAction("&Pick Points Mode", self, checkable=True)
        self._pick_points_action.toggled.connect(self._on_pick_points_toggled)
        points_menu.addAction(self._pick_points_action)
        auto_trace_action = points_menu.addAction("&Auto-Trace Curve by Color...")
        auto_trace_action.triggered.connect(self.start_auto_trace_pick)

        perspective_menu = self.menuBar().addMenu("Pe&rspective")
        correct_action = perspective_menu.addAction("&Correct Perspective...")
        correct_action.triggered.connect(self.start_perspective_pick)

    def open_image_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "Open plot image", "", _IMAGE_FILE_FILTER)
        if not path_str:
            return
        self.open_image(Path(path_str))

    def open_image(self, path: Path) -> None:
        try:
            image = load_image(path)
        except ImageLoadError as exc:
            QMessageBox.critical(self, "Could not open image", str(exc))
            return
        self._raw_image = image
        self._working_image = image
        self.canvas.load_image(image)
        self.project = Project(image_path=path)
        self.project.add_curve(_DEFAULT_CURVE_NAME)
        self._calibration_overlay_items = []
        self._data_point_overlay_items = []
        self._perspective_pick_points = []
        self._perspective_overlay_items = []
        self._calibration_dialog = None
        self._pending_calibration_axis = None
        self._undo_stack.clear()
        self._refresh_point_table()
        self._refresh_curve_panel()

    def reset_project(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No image loaded", "Open an image before resetting.")
            return
        confirmed = QMessageBox.question(
            self,
            "Reset project?",
            "This discards calibration, perspective correction, and all picked/traced "
            "points, and reloads the original image.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self.open_image(self.project.image_path)

    def open_calibration_dialog(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No image loaded", "Open an image before calibrating.")
            return

        dialog = AxisCalibrationDialog(self, image=self._working_image, scene=self.canvas.scene())
        dialog.pickRequested.connect(self._arm_calibration_pick)
        self._calibration_dialog = dialog
        self.canvas.mode = InteractionMode.CALIBRATE

        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                assert dialog.x_calibration is not None
                assert dialog.y_calibration is not None
                self.project.x_axis = dialog.x_calibration
                self.project.y_axis = dialog.y_calibration
                self._refresh_calibration_overlays()
                self._refresh_point_table()
        finally:
            # Idempotent: accept/reject already cleared them. This only covers
            # exec() returning by some other path, so no temporary overlay can
            # survive the dialog and shadow the permanent ones.
            dialog.clear_overlays()
            self._calibration_dialog = None
            self._pending_calibration_axis = None
            self.canvas.mode = (
                InteractionMode.PICK_POINT
                if self._pick_points_action.isChecked()
                else InteractionMode.PAN
            )

    def _on_pick_points_toggled(self, checked: bool) -> None:
        self.canvas.mode = InteractionMode.PICK_POINT if checked else InteractionMode.PAN

    def _arm_calibration_pick(self, axis: str) -> None:
        self._pending_calibration_axis = axis

    def _on_canvas_clicked(self, x: float, y: float) -> None:
        if self._pending_calibration_axis is not None and self._calibration_dialog is not None:
            pixel = x if self._pending_calibration_axis == "x" else y
            self._calibration_dialog.add_point(self._pending_calibration_axis, pixel)
            self._pending_calibration_axis = None
            return
        if self.canvas.mode is InteractionMode.PERSPECTIVE_PICK:
            self._add_perspective_pick_point(Point(x=x, y=y))
            return
        if self.canvas.mode is InteractionMode.AUTO_TRACE_SAMPLE:
            self._sample_and_trace(Point(x=x, y=y))
            return
        if self.canvas.mode is InteractionMode.PICK_POINT:
            self._add_data_point(Point(x=x, y=y))

    def start_auto_trace_pick(self) -> None:
        if self.project is None or self._working_image is None:
            QMessageBox.information(self, "No image loaded", "Open an image first.")
            return
        self.canvas.mode = InteractionMode.AUTO_TRACE_SAMPLE
        self.statusBar().showMessage("Click on the curve to sample its color.")

    def _sample_and_trace(self, point: Point) -> None:
        self.statusBar().clearMessage()
        self.canvas.mode = (
            InteractionMode.PICK_POINT
            if self._pick_points_action.isChecked()
            else InteractionMode.PAN
        )
        assert self._working_image is not None
        assert self.project is not None

        bgr = sample_color_bgr(self._working_image, point)
        dialog = ColorPickerDialog(bgr, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        traced_points = trace_curve_by_color(
            self._working_image, bgr, tolerance=float(dialog.tolerance)
        )
        if not traced_points:
            QMessageBox.information(
                self, "No curve found", "No pixels matched that color within tolerance."
            )
            return

        curve = Curve(
            name=f"Auto Curve {len(self.project.curves) + 1}",
            points=traced_points,
            source="auto",
        )
        self.project.curves.append(curve)
        self.project.active_curve_index = len(self.project.curves) - 1
        self._refresh_point_table()
        self._refresh_data_point_overlays()
        self._refresh_curve_panel()

    def start_perspective_pick(self) -> None:
        if self.project is None or self._raw_image is None:
            QMessageBox.information(self, "No image loaded", "Open an image first.")
            return
        self._perspective_pick_points = []
        self._clear_perspective_overlays()
        self.canvas.mode = InteractionMode.PERSPECTIVE_PICK
        self.statusBar().showMessage(
            "Click the 4 corners of the chart area, in order: "
            "top-left, top-right, bottom-right, bottom-left."
        )

    def _add_perspective_pick_point(self, point: Point) -> None:
        scene = self.canvas.scene()
        marker = make_data_point_marker(point.x, point.y, _PERSPECTIVE_POINT_COLOR)
        scene.addItem(marker)
        self._perspective_overlay_items.append(marker)
        self._perspective_pick_points.append(point)
        if len(self._perspective_pick_points) < _PERSPECTIVE_CORNER_COUNT:
            return
        self._finish_perspective_pick()

    def _finish_perspective_pick(self) -> None:
        self.statusBar().clearMessage()
        self.canvas.mode = InteractionMode.PAN
        assert len(self._perspective_pick_points) == _PERSPECTIVE_CORNER_COUNT
        top_left, top_right, bottom_right, bottom_left = self._perspective_pick_points
        self._perspective_pick_points = []
        self._clear_perspective_overlays()

        confirmed = QMessageBox.question(
            self,
            "Apply perspective correction?",
            "This replaces the working image with a straightened version and "
            "resets any existing calibration and picked points.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        assert self.project is not None
        assert self._raw_image is not None
        corners = (top_left, top_right, bottom_right, bottom_left)
        output_size = estimate_output_size(corners)
        perspective = PerspectiveTransform(src_points=corners, output_size=output_size)
        warped = perspective.warp_image(self._raw_image)

        image_path = self.project.image_path
        self.project = Project(image_path=image_path, perspective=perspective)
        self.project.add_curve(_DEFAULT_CURVE_NAME)
        self._working_image = warped
        self.canvas.load_image(warped)
        self._calibration_overlay_items = []
        self._data_point_overlay_items = []
        self._undo_stack.clear()
        self._refresh_point_table()
        self._refresh_curve_panel()

    def _clear_perspective_overlays(self) -> None:
        scene = self.canvas.scene()
        for item in self._perspective_overlay_items:
            scene.removeItem(item)
        self._perspective_overlay_items = []

    def _add_data_point(self, point: Point) -> None:
        if self.project is None or self.project.active_curve is None:
            return
        command = AddPointCommand(self.project.active_curve, point, self._on_points_changed)
        self._undo_stack.push(command)

    def _on_points_changed(self) -> None:
        self._refresh_point_table()
        self._refresh_data_point_overlays()

    def _on_curve_selected(self, index: int) -> None:
        if self.project is None or index < 0:
            return
        self.project.active_curve_index = index
        self._refresh_point_table()
        self._refresh_data_point_overlays()

    def _on_add_curve_requested(self) -> None:
        if self.project is None:
            return
        self.project.add_curve(f"Curve {len(self.project.curves) + 1}")
        self._refresh_point_table()
        self._refresh_data_point_overlays()
        self._refresh_curve_panel()

    def _on_delete_curve_requested(self) -> None:
        if self.project is None or not self.project.curves:
            return
        if len(self.project.curves) == 1:
            QMessageBox.information(self, "Can't delete", "A project needs at least one curve.")
            return
        del self.project.curves[self.project.active_curve_index]
        self.project.active_curve_index = min(
            self.project.active_curve_index, len(self.project.curves) - 1
        )
        self._refresh_point_table()
        self._refresh_data_point_overlays()
        self._refresh_curve_panel()

    def _on_resample_requested(self) -> None:
        if self.project is None or self.project.active_curve is None:
            QMessageBox.information(
                self, "Nothing to resample", "Open an image and pick points first."
            )
            return
        if not self.project.is_calibrated():
            QMessageBox.warning(
                self, "Axes not calibrated", "Calibrate both axes before resampling."
            )
            return
        curve = self.project.active_curve
        if len(curve.points) < _MIN_RESAMPLE_POINTS:
            QMessageBox.information(
                self,
                "Not enough points",
                f"Resampling needs at least {_MIN_RESAMPLE_POINTS} points on the "
                f"selected curve, but it has {len(curve.points)}.",
            )
            return

        dialog = ResampleDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            resampled = resample_curve_to_step(curve.points, self.project.transform(), dialog.step)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not resample", str(exc))
            return
        self._undo_stack.push(ResampleCurveCommand(curve, resampled, self._on_points_changed))

    def save_project_dialog(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No project", "Open an image first.")
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save project", "", "Plot Digitizer Project (*.json)"
        )
        if not path_str:
            return
        save_project(self.project, Path(path_str))

    def open_project_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "Plot Digitizer Project (*.json)"
        )
        if not path_str:
            return
        project = load_project(Path(path_str))
        try:
            image = load_image(project.image_path)
        except ImageLoadError as exc:
            QMessageBox.critical(self, "Could not open project image", str(exc))
            return

        self._raw_image = image
        working_image = project.perspective.warp_image(image) if project.perspective else image
        self._working_image = working_image
        self.canvas.load_image(working_image)
        self.project = project
        self._undo_stack.clear()
        self._refresh_point_table()
        self._refresh_calibration_overlays()
        self._refresh_data_point_overlays()
        self._refresh_curve_panel()

    def _refresh_curve_panel(self) -> None:
        names = [curve.name for curve in self.project.curves] if self.project is not None else []
        active_index = self.project.active_curve_index if self.project is not None else -1
        self._curve_panel.set_curves(names, active_index)

    def export_csv_dialog(self) -> None:
        if self.project is None or self.project.active_curve is None:
            QMessageBox.information(
                self, "Nothing to export", "Open an image and pick points first."
            )
            return
        if not self.project.is_calibrated():
            QMessageBox.warning(
                self, "Axes not calibrated", "Calibrate both axes before exporting."
            )
            return
        path_str, _ = QFileDialog.getSaveFileName(self, "Export points to CSV", "", "CSV (*.csv)")
        if not path_str:
            return
        export_curve_csv(self.project.active_curve, self.project.transform(), Path(path_str))

    def _refresh_point_table(self) -> None:
        curve = self.project.active_curve if self.project is not None else None
        transform = None
        if self.project is not None and self.project.is_calibrated():
            transform = self.project.transform()
        self._point_table_model.set_source(curve, transform)

    def _refresh_calibration_overlays(self) -> None:
        scene = self.canvas.scene()
        for item in self._calibration_overlay_items:
            scene.removeItem(item)
        self._calibration_overlay_items = []
        if self.project is None:
            return

        rect = scene.sceneRect()
        for pixel, _value in self.project.x_axis.reference_points:
            line = make_vertical_reference_line(pixel, rect.height(), _X_REFERENCE_COLOR)
            scene.addItem(line)
            self._calibration_overlay_items.append(line)
        for pixel, _value in self.project.y_axis.reference_points:
            line = make_horizontal_reference_line(pixel, rect.width(), _Y_REFERENCE_COLOR)
            scene.addItem(line)
            self._calibration_overlay_items.append(line)

    def _refresh_data_point_overlays(self) -> None:
        scene = self.canvas.scene()
        for item in self._data_point_overlay_items:
            scene.removeItem(item)
        self._data_point_overlay_items = []
        if self.project is None or self.project.active_curve is None:
            return

        for point in self.project.active_curve.points:
            marker = make_data_point_marker(point.x, point.y, _DATA_POINT_COLOR)
            scene.addItem(marker)
            self._data_point_overlay_items.append(marker)
