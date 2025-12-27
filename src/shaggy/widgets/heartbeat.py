from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import QObject, Signal, QThread, Slot

import zmq

from shaggy.transport import library

class HeartbeatStatus(QWidget):

    def __init__(self):
        super().__init__()

        self.heartbeat_indicator = QLabel("Heartbeat")
        self.heartbeat_indicator.setStyleSheet("""background-color: #FF0000; """)
        self.heartbeat_indicator.setMargin(4)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(self.heartbeat_indicator)

        self.heartbeat_worker = HeartbeatWorker()
        self.heartbeat_thread = QThread()
        self.heartbeat_worker.moveToThread(self.heartbeat_thread)
        self.heartbeat_worker.status.connect(self.set_heartbeat_status)
        self.heartbeat_thread.started.connect(self.heartbeat_worker.run)
        self.heartbeat_thread.start()

    def set_heartbeat_status(self, heartbeat_status):
        if heartbeat_status:
            self.heartbeat_indicator.setStyleSheet("""background-color: #00FF00; """)
        else:
            self.heartbeat_indicator.setStyleSheet("""background-color: #FF0000; """)


class HeartbeatWorker(QObject):
    status = Signal(bool)

    def __init__(self, context: zmq.Context = None):
        super().__init__()
        self.context = context or zmq.Context.instance()
        self.last_heartbeat = 0
        self.timeout_ms = 3000

    @Slot()
    def run(self):
        bridge_socket = self.context.socket(zmq.SUB)
        bridge_socket.bind(library.get_bridge_connection(library.LOCAL_HOST))
        bridge_socket.setsockopt(zmq.SUBSCRIBE, b"heartbeat")
        poller = zmq.Poller()
        poller.register(bridge_socket, zmq.POLLIN)

        while True:
            socks = dict(poller.poll(self.timeout_ms))
            if socks.get(bridge_socket) == zmq.POLLIN:
                message = bridge_socket.recv_multipart()
                self.status.emit(True)
            else:
                self.status.emit(False)
