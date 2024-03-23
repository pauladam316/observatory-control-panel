import serial
import struct
from dataclasses import dataclass

sent = False
data_buffer = bytearray()

MAX_BUFFER_SIZE = 1024
PACKET_SIZE_BYTES = 19
# Sync pattern to look for
sync_pattern = "505050"
@dataclass
class RoofTelem:
    h_bridge_current: float = 0
    voltage_5v: float = 0
    voltage_12v: float = 0
    raise_1_sw: bool = 0
    raise_2_sw: bool = False
    lower_1_sw: bool = False
    lower_2_sw: bool = False


class SerialManager:
    def __init__(self, device_path, packet_size_bytes):
        self.device_path = device_path
        self.data_buffer = bytearray()
        self.packet_size_bytes = packet_size_bytes
        self.port = None
        self.connected = False

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
        super().__init__(device_path, 19)
        self.last_data = RoofTelem()
       
    def parse_data(self, packet: bytearray):
        if len(packet) != PACKET_SIZE_BYTES-3:
            print(f"Error! invalid packet size {len(packet)}")
        struct_format = "fffBBBB"
        deserialized_data = RoofTelem(*struct.unpack(struct_format, packet))
        return deserialized_data

    def zero_data(self):
       return RoofTelem()