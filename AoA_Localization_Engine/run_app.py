from uart_datalogger import DataLogger
from gui import MainWindow, Communicate
from queue import Queue

from PyQt5 import QtWidgets

import sys
import time
import threading

def updateWorker(window, log_queue):
    
    # src = Communicate()
    # src.signal.connect(window.update_callback)
    while not window.close.isSet():
        if(not log_queue.empty):
            print(log_queue.get())
            # src.signal.emit((0,0))

# def worker(window):
#     i = 0
#     while i<30:
#         print("Still working")
#         print(f"Close: {window.close.is_set()}")
#         time.sleep(1)
#         i+=1

if __name__== '__main__':

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()

    logger = DataLogger(window.close)
    logger.start()

    sys.exit(app.exec())

    # update_thread = threading.Thread(name = 'update_thread', target = updateWorker, daemon = True, args = (window, logger.queue, ))
    # update_thread.start()

    # work = threading.Thread(name = 'work', target = worker, args = (window,))
    # work.start()

    # print("Sleep #1")
    # time.sleep(10)
    # print(logger.queue.get())
    # print("Sleep #2")
    # time.sleep(10)
    # print(logger.queue.get())
    # logger.suspend = True
    # logger.join()
        