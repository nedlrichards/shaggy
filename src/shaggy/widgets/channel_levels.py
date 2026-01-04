import matplotlib
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ChannelLevel(QWidget):
    """Sound meter for all channels."""

    class LevelMeter(QWidget):
        """Sound meter for one channel."""

        def __init__(self):
            """Setup sound meter display."""
            super().__init__()
            self.min_bar_height = 25
            self.setMinimumSize(0, self.min_bar_height)
            self.color_map = matplotlib.colormaps["YlOrRd"]
            self.max_db = 0.0
            self.min_db = -50.0
            self.level = self.min_db

        def setLevel(self, level):
            """Update meter."""
            self.level = level
            self.update()

        def paintEvent(self, event):
            """Refresh display."""
            normalized = (self.level - self.min_db) / (self.max_db - self.min_db)
            normalized = max(0.0, min(1.0, normalized))
            color = self.color_map(normalized)
            r = int(color[0] * 255)
            g = int(color[1] * 255)
            b = int(color[2] * 255)

            painter = QtGui.QPainter(self)
            bar_height = int(self.height() * normalized)
            painter.fillRect(
                0, self.height() - bar_height, 100, bar_height, QtGui.QColor(r, g, b)
            )

    def __init__(self, label):
        """Sound level display for all channels."""
        super().__init__()
        self.meter = self.LevelMeter()
        self.label = QLabel(label)
        self.label.setStyleSheet(
            "color: white; font-size: 20px; text-align: center; background-color: blue;"
        )
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.meter)
        box.addWidget(self.label)
        self.setLayout(box)
