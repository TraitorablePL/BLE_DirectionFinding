import threading
import matplotlib
import numpy as np

from PyQt5 import QtWidgets
from PyQt5.QtCore import *

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.animation import TimedAnimation
from matplotlib.lines import Line2D

from mpl_toolkits.axisartist.axislines import AxesZero

class Communicate(QObject):
    signal = pyqtSignal(object)

class PlotCanvas(FigureCanvasQTAgg, TimedAnimation):

    def __init__(self, parent=None, width=10, height=10, dpi=100):
        self.sc = Figure(figsize=(16, 10), dpi=100)
        self.ax = self.sc.add_subplot(axes_class=AxesZero)
        self.x = 0
        self.y = 0
        self.marker = Line2D([], [], color='red', marker='o', markeredgecolor='r')
        
        self.ax.grid(True)
        self.ax.set_xlim(-90,90)
        self.ax.set_ylim(-90,90)
        self.ax.add_line(self.marker)
        self.ax.axis["xzero"].set_visible(True)
        self.ax.axis["yzero"].set_visible(True)
        self.ax.axis["left"].set_visible(False)
        self.ax.axis["right"].set_visible(False)
        self.ax.axis["bottom"].set_visible(False)   
        self.ax.axis["top"].set_visible(False)
        ticks = np.arange(-90,91,30)
        self.ax.xaxis.set_ticks(ticks, [f"${i}\degree$" for i in ticks])
        self.ax.yaxis.set_ticks(ticks, [f"${i}\degree$" for i in ticks])
        self.ax.set_title("Direction radar")

        FigureCanvasQTAgg.__init__(self, self.sc)
        TimedAnimation.__init__(self, self.sc, interval = 100, blit = True)

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

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.close = threading.Event()
        self.sc = PlotCanvas(self, width=10, height=10, dpi=100)
        self.setCentralWidget(self.sc)
        self.show()

    def closeEvent(self, event):
        print("GUI done!")
        self.close.set()
        return

    def updateCallback(self, values):
        self.sc.updateMarker(values)
        return
        