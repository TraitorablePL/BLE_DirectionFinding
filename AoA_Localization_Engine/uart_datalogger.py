import datetime
import time
import sys
import serial
import json
import threading

class UART_Logger:
    def __init__(self, port='COM4', baudrate='115200'):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.start_time = None

    def connect(self):
        try:
            self.serial = serial.Serial()
            self.serial.baudrate = self.baudrate
            self.serial.port = self.port
            self.serial.timeout = None
            self.serial.open()
        except (OSError, serial.SerialException):
            print(f"Problem: {serial.SerialException}")
            pass

    def disconnect(self):
        if(self.serial and not self.serial.is_open):
            self.serial.close()

    def _trigger(self, event):
        while not event.isSet():
            line = self.readline()
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

    # Read line from stream without '\r\n'
    def readline(self):
        return self.serial.read_until(b'\r\n')[:-2].decode("utf-8")

    # Get current time and date
    def timestamp(self):
        self.start_time = datetime.datetime.now()
        return self.start_time.strftime("%Y.%m.%d_%H:%M:%S.%f")

    # Get time difference from start
    def timestamp_diff(self):
        now = datetime.datetime.now()
        diff = now - self.start_time
        return f"+{diff}"

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

# Update tokens in dictionary with received UART msg
def update_tokens(header, line):
    tokens = [sub.split(':', 1) for sub in (line[1:].split(','))]
    for i in range(len(tokens)): # zle dziala
        if tokens[i][0] in header:
            header[tokens[i][0]] = tokens[i][1]

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

    log_data = {
        "Header" : None,
        "Records" : []
    }
    Logger = UART_Logger()
    Logger.connect()
    state = "init"

    print("Waiting for header...")
    if(Logger.trigger(10)):

        print("Header found. Starting logging...")
        print("Type 'exit' to end logging")

        header = {
            "Timestart" : None,
            "Addr" : None,
            "Interval" : None,
            "PHY" : None,
            "Pattern" : None,
            "Samples" : None,
            "Slot" : None
        }

        sample = {
            "Timediff" : None,
            "RSSI" : None,
            "IQ" : None
        }

        while (not user_event.isSet()):
            line = Logger.readline()

            if(state == "init" and line[:5] == "$Addr"):
                header["Timestart"] = Logger.timestamp()
                update_tokens(header, line)
                state = "packet_info"

            elif(state == "packet_info" and line[:8] == "$Pattern"):
                update_tokens(header, line)
                log_data["Header"] = header
                state = "iq_sampling"

            elif(state == "iq_sampling" and line[:8] == "$Pattern"):
                #TODO: Fix IQ formating inside update_tokens function
                sample["Timediff"] = Logger.timestamp_diff()
                update_tokens(sample, line)
                log_data["Records"].append(sample)
                state = "iq_sampling"

            else:
                pass

        print("End of logging")
        
    else:
        print("Failed to find header msg")

    print(f"Recorded data: {log_data}")

    Logger.disconnect()
