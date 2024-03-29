from uart_datalogger import DataLogger
from gui import MainWindow, Communicate
from localization_engine import Localization

from queue import Queue
from PyQt5.QtWidgets import QApplication
from threading import Thread

import sys
import time

def updateWorker(event_close, queue):
    
    localizer = Localization()
    src = Communicate()
    src.signal.connect(window.updateCallback)

    while not event_close.isSet():
        (azim, elev) = localizer.locate_basic(queue.get())
        if(azim != 0 or elev != 0):
            azim -= 90
            elev -= 90
            print(f"Azimuth:{azim}, Elevation:{elev}")
            src.signal.emit((azim, elev))
        time.sleep(0.1) # Release some time for another work
    print("Updater done!")

if __name__== '__main__':
    data_queue = Queue()
    app = QApplication(sys.argv)
    window = MainWindow()

    logger = DataLogger(window.close, data_queue)
    logger.start()

    update_thread = Thread(name = 'update_thread', target = updateWorker, args = (window.close, data_queue))
    update_thread.start()

    sys.exit(app.exec())
