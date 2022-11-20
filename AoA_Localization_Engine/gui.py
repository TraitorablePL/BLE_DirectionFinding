import threading
import matplotlib
import numpy as np

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.animation import TimedAnimation
from matplotlib.lines import Line2D

class Communicate(QObject):
    signal = pyqtSignal(object)

class PlotCanvas(FigureCanvasQTAgg, TimedAnimation):

    def __init__(self, parent=None, width=10, height=10, dpi=100):
        self.x = 0
        self.y = 0
        self.sc = Figure(figsize=(10, 10), dpi=100)
        self.ax = self.sc.add_subplot()
        self.marker = Line2D([], [], color='red', marker='o', markeredgecolor='r')
        self.setupLayout()
        FigureCanvasQTAgg.__init__(self, self.sc)
        TimedAnimation.__init__(self, self.sc, interval = 100, blit = True)

    def setupLayout(self):
        self.ax.grid(True)
        self.ax.set_xlim(-90,90)
        self.ax.set_ylim(-90,90)
        self.ax.add_line(self.marker)
        self.ax.spines["right"].set_visible(False)
        self.ax.spines["top"].set_visible(False)  
        self.ax.spines['left'].set_position('zero')
        self.ax.spines['bottom'].set_position('zero')
        self.ax.xaxis.set_label_coords(0, -0.03)
        self.ax.yaxis.set_label_coords(-0.03, 0)
        self.ax.set_ylabel('Elevation')
        self.ax.set_xlabel('Azimuth')
        ticks = np.arange(-90,91,30)
        self.ax.xaxis.set_ticks(ticks, [f"${i}\degree$" for i in ticks])
        self.ax.yaxis.set_ticks(ticks, [f"${i}\degree$" for i in ticks])
        self.ax.set_title("Direction radar")

    def new_frame_seq(self):
        return iter(range(1))

    def _init_draw(self):
        self.marker.set_data([], [])
        return

    def _step(self, *args):
        try:
            TimedAnimation._step(self, *args)
        except Exception as e:
            print("Step exception")
            TimedAnimation._stop(self)
            pass
        return

    def _draw_frame(self, framedata):
        self.marker.set_data(self.x, self.y)
        self._drawn_artists = [self.marker]
        return

    def updateMarker(self, values):
        self.x = values[0]
        self.y = values[1]
        return

class MainWindow(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.close = threading.Event()
        self.setWindowTitle("Direction Finding App")
        self.setGeometry(200, 200, 800, 800)
        self.sc = PlotCanvas(self)
        self.frame = QFrame(self)
        self.top_layout = QGridLayout()
        self.info_layout = QHBoxLayout()
        self.xlabel = QLabel("Azimuth: 0")
        self.ylabel = QLabel("Elevation: 0")
        self.info_layout.addWidget(self.xlabel)
        self.info_layout.addWidget(self.ylabel)
        self.top_layout.addLayout(self.info_layout, *(0,0))
        self.top_layout.addWidget(self.sc, *(1,0))
        self.frame.setLayout(self.top_layout)
        self.setupLayout()
        self.show()

    def setupLayout(self):
        self.setCentralWidget(self.frame)
        self.top_layout.setContentsMargins(0,0,0,0)
        self.xlabel.setAlignment(Qt.AlignCenter)
        self.ylabel.setAlignment(Qt.AlignCenter)
        self.frame.setStyleSheet("font-family: Arial; font-size: 24px; background-color: white")

    def closeEvent(self, event):
        print("GUI done!")
        self.close.set()
        return

    def updateCallback(self, values):
        self.sc.updateMarker(values)
        self.xlabel.setText(f"Azimuth: {format(values[0], '.4f')}")
        self.ylabel.setText(f"Elevation: {format(values[1], '.4f')}")
        return
