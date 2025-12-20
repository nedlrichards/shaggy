#!/usr/bin/env -S uv run --script

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst, GstVideo  # noqa E402
Gst.init(None)

from PySide6.QtCore import QMetaObject, Qt

from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import sys
import os
import time

from video_stream import VideoStream

class MainWindow(QWidget):
    """Handle main window."""

    def __init__(self):
        """Main GUI display."""
        super().__init__()

        self.bg = QWidget()
        self.txt_notes = QPlainTextEdit()
        self.record_button = QPushButton("Record")
        self.video = VideoStream()
        self.setup_ui()


    def setup_ui(self):
        """Setup user interface."""
        self.setWindowTitle("Acoustic camera recorder")

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        self.bg.setStyleSheet("background-color: black;")
        main_layout.addWidget(self.bg)

        # Video + audio area
        video_vbox = QVBoxLayout(self.bg)

        self.video.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        video_vbox.addWidget(self.video)

        audio_hbox = QHBoxLayout()
        video_vbox.addLayout(audio_hbox)
        # Right side
        right_vbox = QVBoxLayout()
        main_layout.addLayout(right_vbox)

        self.txt_notes.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        right_vbox.addWidget(QLabel("Notes:"))
        right_vbox.addWidget(self.txt_notes)

        # Record buttons
        record_btn_layout = QHBoxLayout()
        right_vbox.addLayout(record_btn_layout)

        self.record_button.setMinimumHeight(50)
        self.record_button.clicked.connect(self.video.on_record_click)

        record_btn_layout.addWidget(self.record_button)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.showMaximized()
    window.show()
    sys.exit(app.exec())
