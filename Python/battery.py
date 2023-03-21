import asyncio
import struct
import sys
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from telegraf.client import TelegrafClient

telegrafClient = TelegrafClient(host='127.0.0.1', port=8094)

# Used LightBlue to find the UUIDs for the services
RESET_UUID = "f000ffd1-0451-4000-b000-000000000000"
RX_UUID = "0000ffd1-0000-1000-8000-00805f9b34fb"
TX_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"

# The 0xFF ID should get a response from all Renogy smart batteries
VOLT_COMMAND =   bytearray ([0xFF, 0x03, 0x13, 0xB3, 0x00, 0x01])
CURR_COMMAND =     bytearray ([0xFF, 0x03, 0x13, 0xB2, 0x00, 0x01])
CAP_COMMAND  =   bytearray ([0xFF, 0x03, 0x13, 0xB4, 0x00, 0x02])
TEMP_COMMAND =   bytearray ([0xFF, 0x03, 0x13, 0x9A, 0x00, 0x01])

currentCommand = asyncio.Queue()
responseReceived = asyncio.Event()

currentValues = {}

# Calculate the MODBUS CRC and add it to the end of the command to send
def addCRC(msg:str) -> int:
    crc = 0xFFFF
    for n in range(len(msg)):
        crc ^= msg[n]
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return msg + crc.to_bytes(2, 'little')

async def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    command = await currentCommand.get()
    if command == 1:
        print("Voltage: ", data[4]/10.0)
        currentValues['voltage'] = data[4]/10.0
    elif command == 2:
        print("Current: ", struct.unpack('>h',data[3:5])[0]/100.0)
        currentValues['current'] = struct.unpack('>h',data[3:5])[0]/100.0
    elif command == 3:
        print("Temperature: ", struct.unpack('>h',data[3:5])[0]/10.0)
        currentValues['temp'] = struct.unpack('>h',data[3:5])[0]/10.0
    elif command == 4:
        print("Charge: ", struct.unpack('>I',data[3:7])[0]/2000.0)
        currentValues['charge'] = struct.unpack('>I',data[3:7])[0]/2000.0
    responseReceived.set()


async def readBattery(address):
    client = BleakClient(address)
    numTries = 0
    tryAgain = True
    # The battery can only connect to one device at a time, so if it's already connected to my phone or something this will fail. _Generally_ after 5 tries (10 seconds) it will succeed.
    while (numTries < 5 and tryAgain):
        try:
            await client.connect()
            print("Reading from battery",address)
            # Not sure if this is needed, but the app seems to do it every time you connect so I am too.
            print("Resetting BT module.")
            await client.write_gatt_char(RESET_UUID, b"\0100")
            await client.start_notify(TX_UUID, notification_handler)
            print("Reading Battery Voltage")
            await currentCommand.put(1)
            await client.write_gatt_char(RX_UUID, addCRC(VOLT_COMMAND))    
            await responseReceived.wait()
            responseReceived.clear()
            print("Reading Battery Current")
            await currentCommand.put(2)
            await client.write_gatt_char(RX_UUID, addCRC(CURR_COMMAND))    
            await responseReceived.wait()
            responseReceived.clear()
            print("Reading Battery Temperature")
            await currentCommand.put(3)
            await client.write_gatt_char(RX_UUID, addCRC(TEMP_COMMAND))    
            await responseReceived.wait()
            responseReceived.clear()
            print("Reading Battery Capacity")
            await currentCommand.put(4)
            await client.write_gatt_char(RX_UUID, addCRC(CAP_COMMAND))    
            await responseReceived.wait()
            responseReceived.clear()
            await client.stop_notify(TX_UUID)
            print(currentValues)
            telegrafClient.metric('battery',currentValues,tags={'battery': address})
            tryAgain = False
        except Exception as e:
            print("Aww snap, trying again",numTries)
            print(e)
            numTries = numTries + 1
            await asyncio.sleep(2.0)
        finally:
            await client.disconnect()

async def main(address):
    await readBattery(address)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: python3 battery.py [ADDRESS]")
    else:
        address = sys.argv[1]
        asyncio.run(main(address))

