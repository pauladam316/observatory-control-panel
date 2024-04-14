import serial
import struct
from dataclasses import dataclass
from enum import Enum
import traceback

sent = False
data_buffer = bytearray()

MAX_BUFFER_SIZE = 1024
# Sync pattern to look for
sync_pattern = "505050"

class MotionState(Enum):
    UNKNOWN = 0
    RAISING = 1
    LOWERING = 2
    RAISED = 3
    LOWERED = 4

class RoofCommand(Enum):
    CMD_RAISE_ROOF = 0xAB
    CMD_LOWER_ROOF = 0xCD
    CMD_STOP_ROOF = 0xEF
    CMD_ENGAGE_LOCK = 0x12
    CMD_DISENGAGE_LOCK = 0x34
    STOP_LOCK = 0x56
    CMD_HEARTBEAT = 0xF1

@dataclass
class RoofTelem:
    h_bridge_current: float = 0
    voltage_5v: float = 0
    voltage_12v: float = 0
    raise_1_sw: bool = 0
    raise_2_sw: bool = False
    lower_1_sw: bool = False
    lower_2_sw: bool = False
    roof_state: MotionState = MotionState.UNKNOWN
    lock_state: MotionState = MotionState.UNKNOWN

class SerialManager:
    def __init__(self, device_path, packet_size_bytes):
        self.device_path = device_path
        self.data_buffer = bytearray()
        self.packet_size_bytes = packet_size_bytes
        self.port = None
        self.connected = False

    def send_command(self, command):
        if self.port is None or self.connected == False:
            try:
                self.port = serial.Serial(self.device_path, baudrate=57600, timeout=5)
                self.connected = True
                #set_roof_connected(True)
            except Exception as e:
                pass
                #print(f"unable to open serial port with error {e}")
                #set_roof_connected(False
        else:
            data = bytearray([0x50,0x50,0x50]) + bytearray([command.value])
            self.port.write(data)

    def get_telemetry(self):
        if self.port is None or self.connected == False:
            try:
                self.port = serial.Serial(self.device_path, baudrate=57600, timeout=5)
                self.connected = True
                #set_roof_connected(True)
            except Exception as e:
                pass
                #print(f"unable to open serial port with error {e}")
                #set_roof_connected(False)
            return self.zero_data()
        else:       
            try:
                # Read all available bytes from the serial port
                if self.port.in_waiting > 0:
                    data = self.port.read(self.port.in_waiting)
                    self.data_buffer += data
                    if len(self.data_buffer) > MAX_BUFFER_SIZE:
                        # Optionally, log a  warning here
                        self.data_buffer = self.data_buffer[-MAX_BUFFER_SIZE:]  # Keep the last MAX_BUFFER_SIZE bytes
                        #print("max size exceeded!")
                    # Look for the sync pattern in the buffer
                    sync_index = int(self.data_buffer.hex().rfind(sync_pattern) / 2)
                    if sync_index != -1:
                        # Check if there are at least 10 bytes following the sync pattern
                        if len(self.data_buffer) - sync_index >= self.packet_size_bytes:  # 3 bytes of sync pattern + 10 bytes of data
                            # Extract and remove the 13 bytes (sync pattern + data) from the buffer
                            packet = self.data_buffer[sync_index:sync_index+self.packet_size_bytes]
                            data_buffer = self.data_buffer[sync_index+self.packet_size_bytes:]

                            # Parse the data (excluding the sync pattern)
                            self.last_data =  self.parse_data(packet[3:])         
                            return self.last_data   
            except Exception as e:
                print(f"unable to read from serial port with error {e}")
                self.connected = False
                return self.zero_data()
             
                #data = [0 for i in range(NUM_TELEM_ELEMENTS)]
                #set_roof_connected(False)
            return self.last_data


class RoofCommManager(SerialManager):  
    def __init__(self, device_path):
        super().__init__(device_path, 21)
        self.last_data = RoofTelem()
        self.on_raised_callbacks = []
        self.on_lowered_callbacks = []
        self.on_locked_callbacks = []
        self.on_unlocked_callbacks = []

    def parse_data(self, packet: bytearray):
        if len(packet) != self.packet_size_bytes-3:
            print(f"Error! invalid packet size {len(packet)}")
        struct_format = "fffBBBBBB"
        deserialized_data = RoofTelem(*struct.unpack(struct_format, packet))
        deserialized_data.roof_state = MotionState(deserialized_data.roof_state)
        deserialized_data.lock_state = MotionState(deserialized_data.lock_state)
        if deserialized_data.roof_state == MotionState.RAISED and deserialized_data.roof_state != self.last_data.roof_state:
            for callback in self.on_raised_callbacks:
                callback()
        if deserialized_data.roof_state == MotionState.LOWERED and deserialized_data.roof_state != self.last_data.roof_state:
            for callback in self.on_lowered_callbacks:
                callback()
        if deserialized_data.lock_state == MotionState.RAISED and deserialized_data.lock_state != self.last_data.lock_state:
            for callback in self.on_locked_callbacks:
                callback()
        if deserialized_data.lock_state == MotionState.LOWERED and deserialized_data.lock_state != self.last_data.lock_state:
            for callback in self.on_unlocked_callbacks:
                callback()

        self.last_data = deserialized_data
        return deserialized_data
    
    def on_raised(self, callback):
        self.on_raised_callbacks.append(callback)

    def on_lowered(self, callback):
        self.on_lowered_callbacks.append(callback)

    def on_locked(self, callback):
        self.on_locked_callbacks.append(callback)

    def on_unlocked(self, callback):
        self.on_unlocked_callbacks.append(callback)

    def raise_roof(self):
        print("Enabling roof raise")
        self.send_command(RoofCommand.CMD_RAISE_ROOF)

    def lower_roof(self):
        print("Enabling roof lower")
        self.send_command(RoofCommand.CMD_LOWER_ROOF)

    def stop_roof(self):
        print("Stopping roof")
        self.send_command(RoofCommand.CMD_STOP_ROOF)

    def engage_lock(self):
        print("Engaging Lock")
        self.send_command(RoofCommand.CMD_ENGAGE_LOCK)

    def disengage_lock(self):
        print("Disengaging Lock")
        self.send_command(RoofCommand.CMD_DISENGAGE_LOCK)

    def stop_lock(self):
        print("Stopping Lock")
        self.send_command(RoofCommand.STOP_LOCK)

    def update(self):
        pass
        self.send_command(RoofCommand.CMD_HEARTBEAT)

    def zero_data(self):
       return RoofTelem()