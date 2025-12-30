import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QWidget, QVBoxLayout
from PySide6.QtCore import QThread, QObject, Signal

from shaggy.widgets.heartbeat import HeartbeatStatus


class MainWindow(QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__()

        self.setGeometry(100, 100, 500, 300)

        self.title = 'Acoustic Camera'
        self.set_title()

        self.path = None

        # status bar
        self.status_bar = self.statusBar()

        # display the a message in 5 seconds
        self.status_bar.showMessage('Ready', 5000)

        # add a permanent widget to the status bar
        self.heartbeat_status = HeartbeatStatus()
        self.status_bar.addPermanentWidget(self.heartbeat_status)
        self.show()


    def set_title(self, filename=None):
        title = f"{filename if filename else 'Untitled'} - {self.title}"
        self.setWindowTitle(title)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
