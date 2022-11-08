import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import functools
import numpy as np
import random as rd
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.figure import Figure
from matplotlib.animation import TimedAnimation
from matplotlib.lines import Line2D
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from mpl_toolkits.axisartist.axislines import AxesZero
import time
import threading

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        # Define the geometry of the main window
        self.setGeometry(300, 300, 800, 800)
        self.setWindowTitle("Direction Finding RadarApp")
        # Create FRAME_A
        self.FRAME_A = QFrame(self)
        self.FRAME_A.setStyleSheet("QWidget { background-color: %s }" % QColor(210,210,235,255).name())
        self.LAYOUT_A = QGridLayout()
        self.FRAME_A.setLayout(self.LAYOUT_A)
        self.setCentralWidget(self.FRAME_A)
        self.myFig = CustomFigCanvas()
        self.LAYOUT_A.addWidget(self.myFig, *(0,1))
        # Add the callbackfunc to ..
        myDataLoop = threading.Thread(name = 'myDataLoop', target = dataSendLoop, daemon = True, args = (self.addData_callbackFunc,))
        myDataLoop.start()
        self.show()
        return

    def addData_callbackFunc(self, values):
        self.myFig.addData(values)
        return

''' End Class '''

class CustomFigCanvas(FigureCanvas, TimedAnimation):
    def __init__(self):
        # self.addedData = []
        print(matplotlib.__version__)
        # Basic points on plot that are later updated with current value
        self.x = 0
        self.y = 0
        # The window
        self.fig = Figure(figsize=(16, 10), dpi=100)
        self.ax = self.fig.add_subplot(axes_class=AxesZero)
        # self.ax settings
        for direction in ["xzero", "yzero"]:
            # adds X and Y-axis from the origin
            self.ax.axis[direction].set_visible(True)
        for direction in ["left", "right", "bottom", "top"]:
            # hides borders
            self.ax.axis[direction].set_visible(False)
            self.ax.set_xticklabels([])
        # TODO position of labels needs to be fixed
        # self.ax.set_xlabel('time')
        # self.ax.set_ylabel('raw data')
        self.marker = Line2D([], [], color='red', marker='o', markeredgecolor='r')
        self.ax.add_line(self.marker)
        self.ax.grid(True)
        self.ax.set_title("Direction radar")
        self.ax.set_xlim(-90,90)
        self.ax.set_ylim(-90,90)
        ticks = np.arange(-90,91,30)
        self.ax.xaxis.set_ticks(ticks, [f"${i}\degree$" for i in ticks])
        self.ax.yaxis.set_ticks(ticks, [f"${i}\degree$" for i in ticks])
        FigureCanvas.__init__(self, self.fig)
        TimedAnimation.__init__(self, self.fig, interval = 50, blit = True)
        return

    # TODO What is the purpose of frame seq
    def new_frame_seq(self):
        return iter(range(1000))

    def _init_draw(self):
        self.marker.set_data([], [])
        return

    def addData(self, values):
        self.x = values[0]
        self.y = values[1]
        return
        
    def _step(self, *args):
        # Extends the _step() method for the TimedAnimation class.
        try:
            TimedAnimation._step(self, *args)
        except Exception as e:
            self.abc += 1
            print(str(self.abc))
            TimedAnimation._stop(self)
            pass
        return

    def _draw_frame(self, framedata):
        # while(len(self.addedData) > 0):
        #     self.y = np.roll(self.y, -1)
        #     self.y[-1] = self.addedData[0]
        #     del(self.addedData[0])

        self.marker.set_data(self.x, self.y)
        self._drawn_artists = [self.marker]
        return

''' End Class '''

# You need to setup a signal slot mechanism, to
# send data to your GUI in a thread-safe way.
# Believe me, if you don't do this right, things
# go very very wrong..
class Communicate(QObject):
    data_signal = pyqtSignal(object)

''' End Class '''

def dataSendLoop(addData_callbackFunc):
    # Setup the signal-slot mechanism.
    mySrc = Communicate()
    mySrc.data_signal.connect(addData_callbackFunc)

    # Simulate some data
    x = [-60, -45, -30, 30, 45, 60]
    y = [-60, -45, -30, 30, 45, 60]
    
    i = 0
    while(True):
        if(i > len(x)-1):
            i = 0
        time.sleep(0.5)
        mySrc.data_signal.emit((x[i],y[i])) # <- Here you emit a signal!
        i += 1
    ###
###

if __name__== '__main__':
    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create('Plastique'))
    myGUI = MainWindow()
    sys.exit(app.exec())
