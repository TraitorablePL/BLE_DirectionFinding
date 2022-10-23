import datetime
import time
import sys
import serial
import json
import threading
import jsbeautifier
import pathlib

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

    def mcu_reset(self):
        self.write("reset\n")

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

    def write(self, str):
        self.serial.write(str.encode('utf-8'))
        self.serial.flush()

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

    # Save captured log into JSON formatted file
    def write_to_file(self, log_data):
        pathlib.Path("logs").mkdir(exist_ok=True)
        with open(f'logs/log_{self.start_time.strftime("%Y.%m.%d_%H.%M.%S")}.json', 'w', encoding='utf-8') as f:
            opts = jsbeautifier.default_options()
            opts.indent_size = 2
            f.write(jsbeautifier.beautify(json.dumps(log_data), opts))

    # Update tokens in dictionary with received UART msg
    def update_tokens(self, msg_type, data):
        keys_list = list(data)
        for i in range(len(keys_list)):
            key = keys_list[i]
            if key in msg_type:
                msg_type[key] = data[key]

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

    Logger.mcu_reset()
    print("Device reset. Waiting for header...")

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

        while (not user_event.isSet()):
            sample = {
                "Timediff" : None,
                "RSSI" : None,
                "Channel" : None,
                "IQ" : None,
            }

            line = Logger.readline()

            if(line[0] == "$"):
                data = dict(json.loads(line[1:]))

                if(state == "init" and "Addr" in data):
                    print("State: Init")
                    header["Timestart"] = Logger.timestamp()
                    Logger.update_tokens(header, data)
                    state = "packet_info"

                elif(state == "packet_info" and "Pattern" in data):
                    print("State: Packet Info")
                    Logger.update_tokens(header, data)
                    log_data["Header"] = header
                    state = "iq_sampling"

                elif(state == "iq_sampling" and "Pattern" in data):
                    sample["Timediff"] = Logger.timestamp_diff()
                    Logger.update_tokens(sample, data)
                    log_data["Records"].append(sample)
                    state = "iq_sampling"

        print(f"Logs saved to log_{Logger.start_time.strftime('%Y.%m.%d_%H.%M.%S')}.json")
        Logger.write_to_file(log_data)

    else:
        print("Failed to find header msg")

    Logger.disconnect()

    #TODO sometimes wrong decode at beggining of stream or there is no timestart initialized
