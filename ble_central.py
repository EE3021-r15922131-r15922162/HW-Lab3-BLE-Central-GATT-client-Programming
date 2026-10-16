"""BLE Central (GATT client) demo for Raspberry Pi 3 (Linux / BlueZ), using bleak.

Flow: scan -> connect -> list GATT (services / characteristics / descriptors)
      -> enable Indication on Blood Pressure Measurement (0x2A35)
         (BlueZ writes the CCCD 0x2902 with 0x0002)
      -> hold the connection -> stop notify (CCCD back to 0x0000) -> disconnect.
Retries automatically when the connection times out.

Usage:  python ble_central.py <advertised name of the phone app>   (default: michael)
"""
import asyncio
import sys
from bleak import BleakScanner, BleakClient

NAME = sys.argv[1] if len(sys.argv) > 1 else "michael"
TARGET = "00002a35-0000-1000-8000-00805f9b34fb"   # Blood Pressure Measurement (Indicate)
CCCD = "00002902-0000-1000-8000-00805f9b34fb"
HOLD = 15
TRIES = 6


def on_data(sender, data):
    print(f"Indication received: {data.hex()}")


async def run_once(n):
    print(f"\n=== Attempt {n} ===")

    print("[1] Scanning ...")
    found = await BleakScanner.discover(timeout=8.0, return_adv=True)
    for addr, (dev, adv) in found.items():
        name = adv.local_name or dev.name
        if name:
            print(f"    {addr}  RSSI={adv.rssi}  name={name}")
    dev = next((d for d, a in found.values() if (a.local_name or d.name) == NAME), None)
    if dev is None:
        print(f"    '{NAME}' not found")
        return False

    print(f"[2] Connecting to {dev.address} ...")
    client = BleakClient(dev, timeout=15.0)
    try:
        await client.connect()
    except Exception as e:
        print(f"    connect failed: {type(e).__name__}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return False

    try:
        print("    Connected")
        print("[3] GATT services:")
        for s in client.services:
            print(f"    [Service] {s.uuid}")
            for c in s.characteristics:
                print(f"      [Char] {c.uuid} handle=0x{c.handle:04x} props={c.properties}")
                for d in c.descriptors:
                    print(f"        [Desc] {d.uuid} handle=0x{d.handle:04x}")

        char = client.services.get_characteristic(TARGET)
        if char is None:
            print("    target characteristic not found")
            return False
        cccd = next((d for d in char.descriptors if d.uuid == CCCD), None)
        print(f"[4] Target {char.uuid}, CCCD handle=0x{cccd.handle:04x}")
        print("    Enabling Indication -> CCCD will be written as 0x0002")
        await client.start_notify(char, on_data)
        print("    start_notify OK")
        await asyncio.sleep(HOLD)
        await client.stop_notify(char)
        print("    stop_notify done (CCCD back to 0x0000)")
        return True
    except Exception as e:
        print(f"    FAILED: {type(e).__name__}: {e}")
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main():
    for i in range(1, TRIES + 1):
        if await run_once(i):
            print("\nSUCCESS")
            return
        print("Retrying in 8 s ... (toggle the phone's advertising switch if needed)")
        await asyncio.sleep(8)
    print("\nAll attempts failed")


asyncio.run(main())
