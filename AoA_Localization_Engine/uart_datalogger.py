import datetime
import time
import sys
import serial
import json
import threading
import io

class UART_Logger:
    def __init__(self, port='COM4', baudrate='115200'):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.conn = None

    def connect(self):
        try:
            self.serial = serial.Serial()
            self.serial.baudrate = self.baudrate
            self.serial.port = self.port
            self.serial.timeout = 5
            self.serial.open()
            self.conn = io.TextIOWrapper(io.BufferedRWPair(self.serial, self.serial,1))
        except (OSError, serial.SerialException):
            print(f"Problem: {serial.SerialException}")
            pass

    def disconnect(self):
        if(self.serial and not self.serial.is_open):
            self.serial.close()

    def _trigger(self, event):
        while not event.isSet():
            line = self.conn.readline()[:-1]
            if(line == 'Init device tracking'):
                break
    
    # Signal when start header found in stream
    def trigger(self, timeout) -> bool:
        isSuccess = True
        event = threading.Event()
        worker = threading.Thread(target=self._trigger, args=(event,))
        worker.start()
        worker.join(timeout)
        if(worker.is_alive()):
            event.set()
            isSuccess = False
        worker.join()
        return isSuccess

    # Read line from stream without '\n'
    def readline(self):
        return self.conn.readline()[:-1] # remove '\n'

    # Get current time and date
    def timestamp(self):
        now = datetime.datetime.now()
        return now.strftime("%Y.%m.%d_%H.%M.%S")

    # Check available COM ports (windows only)
    def check_ports():
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result

# class JSON_Parser:
#     def __init__(self):
#         pass

# User input thread
def user_input(user_event):
    while True:
        data = input()
        if(data == "exit"):
            user_event.set()
            break
        else:
            print("Type 'exit' to end logging")

# Program core
if __name__ == "__main__":

    user_event = threading.Event()
    user_thread = threading.Thread(target=user_input, args=(user_event,))
    user_thread.start()

    log_buffer = []
    Logger = UART_Logger()
    Logger.connect()

    if(Logger.trigger(10)):
        print("Logging...")
        while (not user_event.isSet()):
        # Data should be parsed to JSON here
            log_buffer.append(Logger.timestamp())
            log_buffer.append(Logger.readline())
        print("End of logging")

    Logger.disconnect()
