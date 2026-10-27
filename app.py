"""Photo Measuring App — calibrated 2D measurement prototype."""
from __future__ import annotations
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QDoubleSpinBox, QFileDialog, QGraphicsPixmapItem,
    QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QMessageBox, QPushButton, QVBoxLayout, QWidget)

@dataclass
class Measurement:
    label: str
    start: QPointF
    end: QPointF
    meters: float

class PhotoView(QGraphicsView):
    points_selected = Signal(QPointF, QPointF)
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
        self.setMinimumSize(700, 480)

    def load_photo(self, path):
        photo = QPixmap(path)
        if photo.isNull():
            return False
        self.canvas.clear()
        self.overlays.clear()
        self.pixmap_item = self.canvas.addPixmap(photo)
        self.pixmap_item.setZValue(-5)
        self.canvas.setSceneRect(QRectF(photo.rect()))
        self.start_point = None
        self.resetTransform()
        self.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        return True

    def set_mode(self, mode):
        self.mode = mode
        self.start_point = None
        self.setCursor(Qt.CursorShape.CrossCursor if mode != 'none' else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.mode != 'none' and self.pixmap_item:
            p = self.mapToScene(event.position().toPoint())
            if not self.pixmap_item.sceneBoundingRect().contains(p):
                return
            if self.start_point is None:
                self.start_point = p
            else:
                start, self.start_point = self.start_point, None
                self.points_selected.emit(start, p)
            return
        super().mousePressEvent(event)

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
        self.start_point = None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Photo Measuring App — v0.1')
        self.resize(1180, 760)
        self.image_path = None
        self.meters_per_pixel = None
        self.calibration_points = None
        self.measurements = []
        self.view = PhotoView()
        self.view.points_selected.connect(self.points_received)

        self.open_button = QPushButton('Open Photo')
        self.open_button.clicked.connect(self.open_photo)
        self.calibrate_button = QPushButton('Calibrate: 2 Points')
        self.calibrate_button.clicked.connect(lambda: self.begin('calibrate'))
        self.measure_button = QPushButton('Measure: A–B')
        self.measure_button.clicked.connect(lambda: self.begin('measure'))
        self.clear_button = QPushButton('Clear Measurements')
        self.clear_button.clicked.connect(self.clear_measurements)
        self.fit_button = QPushButton('Fit Photo')
        self.fit_button.clicked.connect(self.fit_photo)
        self.reference = QDoubleSpinBox()
        self.reference.setRange(0.001, 100000)
        self.reference.setDecimals(3)
        self.reference.setValue(3.000)
        self.reference.setSuffix(' m')
        self.reference.setToolTip('Known physical distance between calibration endpoints')
        self.reference.valueChanged.connect(self.reference_changed)
        self.measure_list = QListWidget()
        self.scale_text = QLabel('Scale: not calibrated')
        self.instructions = QLabel('Open a photo to begin.')
        self.instructions.setWordWrap(True)

        side = QWidget()
        layout = QVBoxLayout(side)
        layout.addWidget(self.open_button)
        layout.addWidget(QLabel('Known reference length:'))
        layout.addWidget(self.reference)
        layout.addWidget(self.calibrate_button)
        layout.addWidget(self.measure_button)
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
        self.meters_per_pixel = None
        self.calibration_points = None
        self.measurements.clear()
        self.measure_list.clear()
        self.scale_text.setText('Scale: not calibrated')
        self.view.set_mode('none')
        self.instructions.setText('Enter known wall length, click Calibrate, then click both ends.')
        self.statusBar().showMessage(f'Loaded {Path(path).name}')

    def begin(self, mode):
        if not self.image_path:
            QMessageBox.information(self, 'Load a photo', 'Open a photo first.')
            return
        if mode == 'measure' and self.meters_per_pixel is None:
            QMessageBox.information(self, 'Calibrate first', 'Define a reference length first.')
            return
        self.view.set_mode(mode)
        self.instructions.setText('Click point 1, then click point 2 on the photo.')
        self.statusBar().showMessage(f'{mode.title()} — select two endpoints')

    def points_received(self, a, b):
        distance_px = math.hypot(b.x()-a.x(), b.y()-a.y())
        if distance_px < 1:
            QMessageBox.warning(self, 'Points too close', 'Choose two distinct points.')
            return
        if self.view.mode == 'calibrate':
            self.calibration_points = (a, b)
            self.apply_calibration()
        elif self.view.mode == 'measure' and self.meters_per_pixel is not None:
            label = self.alpha_label(len(self.measurements))
            meters = distance_px * self.meters_per_pixel
            self.measurements.append(Measurement(label, a, b, meters))
            self.measure_list.addItem(f'Measure {label}: {meters:.3f} m')
            self.view.add_line(a, b, f'{label}: {meters:.3f} m', '#41e090')
            self.statusBar().showMessage(f'Measure {label}: {meters:.3f} m')

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
        self.meters_per_pixel = self.reference.value()/px
        self.render_annotations()
        self.scale_text.setText(f'Scale: {self.meters_per_pixel:.7f} m/image-pixel')
        self.instructions.setText('Scale set. Click Measure and select two endpoints.')
        self.view.set_mode('none')
        self.statusBar().showMessage('Calibration complete.')

    def reference_changed(self, value):
        if self.calibration_points:
            self.apply_calibration()

    def render_annotations(self):
        self.view.clear_annotations()
        if self.calibration_points:
            a, b = self.calibration_points
            self.view.add_line(a, b, f'REF: {self.reference.value():.3f} m', '#ffac4b')
        self.measure_list.clear()
        for measurement in self.measurements:
            if self.meters_per_pixel is not None:
                pixel_length = math.hypot(
                    measurement.end.x()-measurement.start.x(),
                    measurement.end.y()-measurement.start.y())
                measurement.meters = pixel_length * self.meters_per_pixel
            self.view.add_line(measurement.start, measurement.end,
                f'{measurement.label}: {measurement.meters:.3f} m', '#41e090')
            self.measure_list.addItem(
                f'Measure {measurement.label}: {measurement.meters:.3f} m')

    def clear_measurements(self):
        self.measurements.clear()
        self.render_annotations()
        self.statusBar().showMessage('Measurements cleared; calibration retained.')

    def fit_photo(self):
        if self.view.pixmap_item:
            self.view.fitInView(self.view.canvas.sceneRect(),
                                Qt.AspectRatioMode.KeepAspectRatio)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
