import datetime
import time
import sys
import serial
import json
import threading
import jsbeautifier
import pathlib

from queue import Queue

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

    def mcuReset(self):
        self.write("reset\n")

    def _trigger(self, event):
        while not event.isSet():
            line = self.readline()
            if(line == 'Bluetooth initialized'):
                break
    
    # Signal when start header found in stream
    def trigger(self, timeout) -> bool:
        is_success = True
        event = threading.Event()
        worker = threading.Thread(target=self._trigger, args=(event,))
        worker.start()
        worker.join(timeout)
        if(worker.is_alive()):
            event.set()
            is_success = False
        worker.join()
        return is_success

    def write(self, str):
        self.serial.write(str.encode('utf-8'))
        self.serial.flush()

    # Read line from stream without '\r\n'
    def readline(self):
        try:
            out = self.serial.read_until(b'\r\n')[:-2].decode("utf-8")
        except UnicodeDecodeError:
            print("NOK Decode")
            return ""
        else:
            return out

    # Get current time and date
    def getTimestamp(self):
        self.start_time = datetime.datetime.now()
        return self.start_time.strftime("%Y.%m.%d_%H:%M:%S.%f")

    # Get time difference from start
    def getTimestampDiff(self):
        now = datetime.datetime.now()
        diff = now - self.start_time
        return f"+{diff}"

    # Check available COM ports (windows only)
    def checkPorts():
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

    # Save captured log into JSON formatted file
    def write2File(self, log_data):
        pathlib.Path("logs").mkdir(exist_ok=True)
        with open(f'logs/log_{self.start_time.strftime("%Y.%m.%d_%H.%M.%S")}.json', 'w', encoding='utf-8') as f:
            opts = jsbeautifier.default_options()
            opts.indent_size = 2
            f.write(jsbeautifier.beautify(json.dumps(log_data), opts))

    # Update tokens in dictionary with received UART msg
    def updateTokens(self, msg_type, data):
        keys_list = list(data)
        for i in range(len(keys_list)):
            key = keys_list[i]
            if key in msg_type:
                msg_type[key] = data[key]

class DataLogger(threading.Thread):

    def __init__(self, close_event, queue):
        self.close = close_event
        self.data = {"Header" : None, "Records" : []}
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):
        state = "init"

        UART = UART_Logger("COM4", 460800)
        UART.connect()
        UART.mcuReset()

        if(UART.trigger(10)):
            print("Header found. Starting logging...")

            header = {
                "Timestart" : None,
                "Addr" : None,
                "Interval" : None,
                "PHY" : None,
                "Pattern" : None,
                "Samples" : None,
                "Slot" : None
            }

            while (not self.close.isSet()):
                sample = {
                    "Timediff" : None,
                    "RSSI" : None,
                    "Channel" : None,
                    "IQ" : None,
                }

                line = UART.readline()

                if(line[0] == "$"):
                    data = dict(json.loads(line[1:]))

                    if(state == "init" and "Addr" in data):
                        print("State: Init")
                        header["Timestart"] = UART.getTimestamp()
                        UART.updateTokens(header, data)
                        state = "packet_info"

                    elif(state == "packet_info" and "Pattern" in data):
                        print("State: Packet Info")
                        UART.updateTokens(header, data)
                        self.data["Header"] = header
                        state = "iq_sampling"

                    elif(state == "iq_sampling" and "Pattern" in data):
                        sample["Timediff"] = UART.getTimestampDiff()
                        UART.updateTokens(sample, data)
                        self.data["Records"].append(sample)
                        self.queue.put(sample)
                        state = "iq_sampling"

            print(f"Logs saved to log_{UART.start_time.strftime('%Y.%m.%d_%H.%M.%S')}.json")
            UART.write2File(self.data)

        else:
            print("Failed to find header msg")

        UART.disconnect()
        print("Logger done!")
