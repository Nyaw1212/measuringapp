"""Photo Measuring App — calibrated 2D measurement prototype."""
from __future__ import annotations
import math
import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPen, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDoubleSpinBox, QFileDialog, QGraphicsPixmapItem,
    QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QMessageBox, QPushButton, QVBoxLayout, QWidget, QInputDialog)

@dataclass
class Measurement:
    label: str
    start: QPointF
    end: QPointF
    feet: float

class PhotoView(QGraphicsView):
    points_selected = Signal(QPointF, QPointF)
    path_point_selected = Signal(QPointF)
    def __init__(self):
        super().__init__()
        self.canvas = QGraphicsScene(self)
        self.setScene(self.canvas)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor('#20252b')))
        self.pixmap_item = None
        self.start_point = None
        self.mode = 'none'
        self.overlays = []
        self.preview_line = None
        self.preview_text = None
        self.feet_per_pixel = None
        self.distance_function = None
        self.dragging_endpoint = False
        self.setMouseTracking(True)
        self.setMinimumSize(700, 480)

    def load_photo(self, path):
        photo = QPixmap(path)
        if photo.isNull():
            return False
        self.canvas.clear()
        self.overlays.clear()
        self.pixmap_item = self.canvas.addPixmap(photo)
        self.pixmap_item.setZValue(-5)
        bounds = QRectF(photo.rect())
        margin = max(bounds.width(), bounds.height()) * 1.5
        self.canvas.setSceneRect(bounds.adjusted(-margin, -margin, margin, margin))
        self.start_point = None
        self.preview_line = None
        self.preview_text = None
        self.resetTransform()
        self.fitInView(QRectF(photo.rect()), Qt.AspectRatioMode.KeepAspectRatio)
        return True

    def set_mode(self, mode):
        self.mode = mode
        self.start_point = None
        self.clear_preview()
        self.setCursor(Qt.CursorShape.CrossCursor if mode != 'none' else Qt.CursorShape.ArrowCursor)

    def current_anchor(self):
        return self.start_point

    def clear_preview(self):
        for item in (self.preview_line, self.preview_text):
            if item is not None and item.scene() is self.canvas:
                self.canvas.removeItem(item)
        self.preview_line = None
        self.preview_text = None

    def update_preview(self, p):
        anchor = self.current_anchor()
        if anchor is None or self.mode == 'none':
            self.clear_preview()
            return
        self.clear_preview()
        pen = QPen(QColor('#ffeb75'), 2, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.preview_line = self.canvas.addLine(anchor.x(), anchor.y(), p.x(), p.y(), pen)
        self.preview_line.setZValue(20)
        length_px = math.hypot(p.x()-anchor.x(), p.y()-anchor.y())
        length_ft = self.distance_function(anchor, p) if self.distance_function else (length_px * self.feet_per_pixel if self.feet_per_pixel else None)
        label = f'{length_ft:.2f} ft' if length_ft is not None else 'Preview'
        self.preview_text = self.canvas.addSimpleText(label)
        self.preview_text.setBrush(QBrush(QColor('#ffeb75')))
        self.preview_text.setPos((anchor.x()+p.x())/2+8, (anchor.y()+p.y())/2+8)
        self.preview_text.setZValue(21)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.mode != 'none' and self.pixmap_item:
            p = self.mapToScene(event.position().toPoint())
            if self.start_point is None:
                self.start_point = p
                if self.mode == 'continuous':
                    self.path_point_selected.emit(p)
                return
            self.dragging_endpoint = True
            self.update_preview(p)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_point is not None and self.pixmap_item:
            p = self.mapToScene(event.position().toPoint())
            self.update_preview(p)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_endpoint:
            self.dragging_endpoint = False
            p = self.mapToScene(event.position().toPoint())
            a = self.start_point
            if a is not None and math.hypot(p.x()-a.x(), p.y()-a.y()) >= 1:
                self.clear_preview()
                if self.mode == 'continuous':
                    self.start_point = p
                    self.path_point_selected.emit(p)
                else:
                    self.start_point = None
                    self.points_selected.emit(a, p)
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if not self.pixmap_item:
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        if 0.03 <= self.transform().m11() * factor <= 50:
            self.scale(factor, factor)

    def add_line(self, a, b, label, color):
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        line = self.canvas.addLine(a.x(), a.y(), b.x(), b.y(), pen)
        line.setZValue(10)
        self.overlays.append(line)
        for p in (a, b):
            dot = self.canvas.addEllipse(p.x()-3, p.y()-3, 6, 6,
                QPen(QColor(color)), QBrush(QColor(color)))
            dot.setZValue(11)
            self.overlays.append(dot)
        text = self.canvas.addSimpleText(label)
        text.setBrush(QBrush(QColor(color)))
        text.setPos((a.x()+b.x())/2+7, (a.y()+b.y())/2+7)
        text.setZValue(12)
        self.overlays.append(text)

    def clear_annotations(self):
        for item in self.overlays:
            self.canvas.removeItem(item)
        self.overlays.clear()
        self.clear_preview()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Photo Measuring App — v0.7')
        self.resize(1180, 760)
        self.image_path = None
        self.feet_per_pixel = None
        self.calibration_points = None
        self.axes = {}
        self.measurements = []
        self.paths = []
        self.active_path = []
        self.undo_stack = []
        self.redo_stack = []
        self.view = PhotoView()
        self.view.distance_function = self.distance_ft
        self.view.points_selected.connect(self.points_received)
        self.view.path_point_selected.connect(self.add_path_point)

        self.open_button = QPushButton('Open Photo')
        self.open_button.clicked.connect(self.open_photo)
        self.calibrate_button = QPushButton('Set / Replace Reference')
        self.calibrate_button.clicked.connect(lambda: self.begin('calibrate'))
        self.x_axis_button = QPushButton('Set X Axis (known width)')
        self.x_axis_button.clicked.connect(lambda: self.begin('axis_x'))
        self.z_axis_button = QPushButton('Set Z Axis (known height)')
        self.z_axis_button.clicked.connect(lambda: self.begin('axis_z'))
        self.measure_button = QPushButton('Measure Next Length')
        self.measure_button.clicked.connect(lambda: self.begin('measure'))
        self.continuous_button = QPushButton('Continuous Measurement')
        self.continuous_button.clicked.connect(lambda: self.begin('continuous'))
        self.undo_button = QPushButton('Undo Last Point')
        self.undo_button.clicked.connect(self.undo)
        self.finish_button = QPushButton('Finish Path')
        self.finish_button.clicked.connect(self.finish_path)
        self.clear_button = QPushButton('Clear Measurements')
        self.clear_button.clicked.connect(self.clear_measurements)
        self.fit_button = QPushButton('Fit Photo')
        self.fit_button.clicked.connect(self.fit_photo)
        self.reference = QDoubleSpinBox()
        self.reference.setRange(0.001, 100000)
        self.reference.setDecimals(3)
        self.reference.setValue(10.000)
        self.reference.setSuffix(' ft')
        self.reference.setToolTip('Known physical distance between calibration endpoints')
        self.reference.valueChanged.connect(self.reference_changed)
        self.measure_list = QListWidget()
        self.scale_text = QLabel('Scale: not calibrated')
        self.instructions = QLabel('Open a photo to begin.')
        self.instructions.setWordWrap(True)

        side = QWidget()
        layout = QVBoxLayout(side)
        layout.addWidget(self.open_button)
        layout.addWidget(self.calibrate_button)
        layout.addWidget(self.x_axis_button)
        layout.addWidget(self.z_axis_button)
        layout.addWidget(self.measure_button)
        layout.addWidget(self.continuous_button)
        layout.addWidget(self.undo_button)
        layout.addWidget(self.finish_button)
        layout.addWidget(self.fit_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.scale_text)
        layout.addWidget(self.instructions)
        layout.addWidget(QLabel('Saved measurements:'))
        layout.addWidget(self.measure_list, 1)
        side.setFixedWidth(270)
        container = QWidget()
        main_layout = QHBoxLayout(container)
        main_layout.addWidget(side)
        main_layout.addWidget(self.view, 1)
        self.setCentralWidget(container)
        self.redo_button = QPushButton('Redo')
        self.redo_button.clicked.connect(self.redo)
        layout.insertWidget(5, self.redo_button)
        for keys, action in [('Ctrl+Z', self.undo), ('Ctrl+Y', self.redo),
                             ('Ctrl+Shift+Z', self.redo), ('Return', self.enter_measurement)]:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(action)
        self.statusBar().showMessage('Ready — use a known dimension for calibration.')

    def open_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open Photo', '',
                                              'Images (*.png *.jpg *.jpeg *.bmp *.webp)')
        if not path:
            return
        if not self.view.load_photo(path):
            QMessageBox.warning(self, 'Invalid photo', 'Could not open the image.')
            return
        self.image_path = path
        self.feet_per_pixel = None
        self.view.feet_per_pixel = None
        self.calibration_points = None
        self.axes.clear()
        self.measurements.clear()
        self.paths.clear()
        self.active_path.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.measure_list.clear()
        self.scale_text.setText('Scale: not calibrated')
        self.view.set_mode('none')
        self.instructions.setText('Click Set / Replace Reference, then select two points and enter their actual length.')
        self.statusBar().showMessage(f'Loaded {Path(path).name}')

    def begin(self, mode):
        if not self.image_path:
            QMessageBox.information(self, 'Load a photo', 'Open a photo first.')
            return
        if mode in ('measure', 'continuous') and not self.is_calibrated():
            mode = 'calibrate'
        if self.active_path and mode != 'continuous':
            self.finish_path()
        self.view.set_mode(mode)
        if mode == 'continuous':
            self.instructions.setText('Click consecutive points to trace a path. Finish Path to save it; Undo Last Point to correct it.')
        else:
            self.instructions.setText('Click point 1, then click point 2 on the photo.')
        self.statusBar().showMessage(f'{mode.title()} — click first point, then move or drag the next endpoint')

    def points_received(self, a, b):
        distance_px = math.hypot(b.x()-a.x(), b.y()-a.y())
        if distance_px < 1:
            QMessageBox.warning(self, 'Points too close', 'Choose two distinct points.')
            return
        if self.view.mode in ('axis_x', 'axis_z'):
            key = 'X' if self.view.mode == 'axis_x' else 'Z'
            default = self.axes[key][2] if key in self.axes else (10.0 if key == 'X' else 8.0)
            length, accepted = QInputDialog.getDouble(
                self, f'Set {key} axis', f'Known {key} axis length (feet):',
                default, 0.001, 100000.0, 3)
            if not accepted:
                return
            proposed = dict(self.axes)
            proposed[key] = (a, b, length)
            if len(proposed) == 2:
                x0, x1, _ = proposed['X']
                z0, z1, _ = proposed['Z']
                ux, uy = x1.x()-x0.x(), x1.y()-x0.y()
                vx, vy = z1.x()-z0.x(), z1.y()-z0.y()
                determinant = ux*vy-uy*vx
                if abs(determinant) < 0.02*math.hypot(ux, uy)*math.hypot(vx, vy):
                    QMessageBox.warning(self, 'Invalid axes',
                        'X and Z directions are too close to parallel. Choose two distinct wall directions.')
                    return
            self.axes = proposed
            self.view.set_mode('none')
            self.update_calibration_status()
            self.render_annotations()
            return
        if self.view.mode == 'calibrate':
            length, accepted = QInputDialog.getDouble(self, 'Reference length',
                'Actual distance between selected points (feet):',
                self.reference.value(), 0.001, 100000.0, 3)
            if not accepted:
                self.instructions.setText('Reference cancelled. Select two points to try again.')
                return
            self.reference.setValue(length)
            self.calibration_points = (a, b)
            self.apply_calibration()
        elif self.view.mode == 'measure' and self.feet_per_pixel is not None:
            label = self.alpha_label(len(self.measurements))
            feet = self.distance_ft(a, b)
            self.save_undo()
            self.measurements.append(Measurement(label, a, b, feet))
            self.measure_list.addItem(f'Measure {label}: {feet:.3f} ft')
            self.view.add_line(a, b, f'{label}: {feet:.3f} ft', '#41e090')
            self.statusBar().showMessage(f'Measure {label}: {feet:.3f} ft')

    def add_path_point(self, point):
        if not self.is_calibrated():
            return
        if self.active_path:
            previous = self.active_path[-1]
            if math.hypot(point.x()-previous.x(), point.y()-previous.y()) < 1:
                return
        self.save_undo()
        self.active_path.append(point)
        self.render_annotations()
        self.view.start_point = self.active_path[-1]
        self.statusBar().showMessage(f'Continuous path: {len(self.active_path)} points')

    def snapshot(self):
        return copy.deepcopy((self.measurements, self.paths, self.active_path))

    def save_undo(self):
        self.undo_stack.append(self.snapshot())
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self.restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self.restore(self.redo_stack.pop())

    def restore(self, state):
        self.measurements, self.paths, self.active_path = copy.deepcopy(state)
        self.render_annotations()
        self.view.set_mode('continuous' if self.active_path else 'none')
        if self.active_path:
            self.view.start_point = self.active_path[-1]

    def undo_path_point(self):
        self.undo()

    def enter_measurement(self):
        if not self.image_path:
            return
        if not self.is_calibrated():
            self.begin('calibrate')
            return
        if self.view.mode == 'continuous':
            self.finish_path()
        self.begin('continuous')

    def finish_path(self):
        if self.active_path:
            self.save_undo()
            if len(self.active_path) >= 2:
                self.paths.append(self.active_path.copy())
            self.active_path.clear()
        self.render_annotations()
        if self.view.mode == 'continuous':
            self.view.set_mode('none')

    def is_calibrated(self):
        return len(self.axes) == 2 or self.feet_per_pixel is not None

    def distance_ft(self, a, b):
        dx, dy = b.x()-a.x(), b.y()-a.y()
        if len(self.axes) == 2:
            x0, x1, width = self.axes['X']
            z0, z1, height = self.axes['Z']
            ux, uy = x1.x()-x0.x(), x1.y()-x0.y()
            vx, vy = z1.x()-z0.x(), z1.y()-z0.y()
            determinant = ux*vy-uy*vx
            if abs(determinant) > 1e-9:
                x_feet = (dx*vy-dy*vx)/determinant * width
                z_feet = (ux*dy-uy*dx)/determinant * height
                return math.hypot(x_feet, z_feet)
        return math.hypot(dx, dy) * self.feet_per_pixel if self.feet_per_pixel is not None else None

    def update_calibration_status(self):
        if len(self.axes) == 2:
            self.scale_text.setText('Calibration: X + Z axes (affine wall plane)')
            self.instructions.setText('Two-axis correction active. Measure along the same wall plane.')
        elif self.axes:
            self.scale_text.setText('Calibration: one axis set; select the other axis')
        elif self.feet_per_pixel is not None:
            self.scale_text.setText(f'Scale: {self.feet_per_pixel:.7f} ft/image-pixel')
        else:
            self.scale_text.setText('Scale: not calibrated')

    def draw_path(self, points, title, color):
        if not points:
            return
        if len(points) == 1:
            p = points[0]
            self.view.add_line(p, p, title + ' start', color)
            return
        total = 0.0
        for i in range(1, len(points)):
            a, b = points[i-1], points[i]
            feet = self.distance_ft(a, b)
            total += feet
            self.view.add_line(a, b, f'{i}: {feet:.3f} ft', color)
            self.measure_list.addItem(f'{title} segment {i}: {feet:.3f} ft')
        self.measure_list.addItem(f'{title} TOTAL: {total:.3f} ft')

    @staticmethod
    def alpha_label(index):
        output = ''
        while True:
            index, rem = divmod(index, 26)
            output = chr(65+rem)+output
            if index == 0:
                return output
            index -= 1

    def apply_calibration(self):
        if self.calibration_points is None:
            return
        a, b = self.calibration_points
        px = math.hypot(b.x()-a.x(), b.y()-a.y())
        if px < 1:
            return
        self.feet_per_pixel = self.reference.value()/px
        self.view.feet_per_pixel = self.feet_per_pixel
        self.render_annotations()
        self.update_calibration_status()
        self.instructions.setText('Reference set in feet. Move cursor for a live preview; hold and drag to position the endpoint.')
        self.view.set_mode('none')
        self.statusBar().showMessage('Calibration complete.')

    def reference_changed(self, value):
        if self.calibration_points:
            self.apply_calibration()

    def render_annotations(self):
        self.view.clear_annotations()
        for key, (a, b, length) in self.axes.items():
            self.view.add_line(a, b, f'{key} AXIS: {length:.3f} ft', '#ff6bc1' if key == 'X' else '#7caaff')
        if self.view.mode == 'continuous' and self.active_path:
            self.view.start_point = self.active_path[-1]
        if self.calibration_points:
            a, b = self.calibration_points
            self.view.add_line(a, b, f'REF: {self.reference.value():.3f} ft', '#ffac4b')
        self.measure_list.clear()
        for index, path in enumerate(self.paths, 1):
            self.draw_path(path, f'Path {index}', '#42b9ff')
        if self.active_path:
            self.draw_path(self.active_path, 'Current path', '#e8d66c')
        for measurement in self.measurements:
            if self.feet_per_pixel is not None:
                measurement.feet = self.distance_ft(measurement.start, measurement.end)
            self.view.add_line(measurement.start, measurement.end,
                f'{measurement.label}: {measurement.feet:.3f} ft', '#41e090')
            self.measure_list.addItem(
                f'Measure {measurement.label}: {measurement.feet:.3f} ft')

    def clear_measurements(self):
        if self.measurements or self.paths or self.active_path:
            self.save_undo()
        self.measurements.clear()
        self.paths.clear()
        self.active_path.clear()
        self.render_annotations()
        self.statusBar().showMessage('Measurements cleared; calibration retained.')

    def fit_photo(self):
        if self.view.pixmap_item:
            self.view.fitInView(self.view.pixmap_item.sceneBoundingRect(),
                                Qt.AspectRatioMode.KeepAspectRatio)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
