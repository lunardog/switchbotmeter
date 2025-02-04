from bluepy.btle import Scanner, DefaultDelegate
import binascii
import datetime

SERVICE_UUID = "cba20d00-224d-11e6-9fb8-0002a5d5c51b"


class DevScanner(DefaultDelegate):
    """Device Scanner.

    Iterate trough this device

    Arguments:

        device: HCI device to scan on
        wait: On each scan, how much time to wait for devices
        *args, **kwargs: DefaultDelegate arguments
    """

    def __init__(self, device="hci0", wait=5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wait_time = int(wait)
        self.scanner = Scanner().withDelegate(self)

    def __iter__(self):
        """Use as iterator."""
        return self

    def __next__(self):
        """Each time we call next() over a `DevScanner` object, it will return
        an iterator with the whole currently-available list of devices.
        """
        res = self.scanner.scan(self.wait_time)
        return filter(None, (Device(d) for d in res))


class Device:
    """Represents a device.

    Given a bluepy device object, it gets the scan data and looks for switchbot
    meter information. If found, parses it and populates itself.

    A device will test falsy if it's not a switchbot meter device, wich is used
    with a filter(None, devices) to filter out non-switchbot devices from scan
    data.


    You can access the following data properties after initialization:

        - mac: Device mac
        - model: Device model
        - mode: Device mode
        - date: Date of the current scan
        - temp: Temperature as reported by the meter
        - humidity: Humidity, percentage.
        - data: Complete dict with all the data minus the mac.
    """

    def __init__(self, device):
        self.device = device
        self.mac = None
        self.data = {}
        actions = {
            "16b Service Data": self.set_service_data,
            "Local name": self.set_mac,
            "Complete 128b Services": self.set_mac,
        }
        for (_, key, value) in self.device.getScanData():
            # Load data
            actions.get(key, lambda x: {})(value)

    def __getattr__(self, attr):
        """Enable direct access to data attributes"""
        if attr in self.data:
            return self.data[attr]

    def __bool__(self):
        """Return false if the device is not a switchbot meter"""
        return bool(self.mac and self.data)

    def __repr__(self):
        """Represent data model, temp, humidity and mac."""
        if self.data:
            return (
                f'<{self.data["model"]} ({self.data["mode"]}) '
                f'temp: {self.data["temp"]:.2f} '
                f'humidity: {self.data["humidity"]}%> ({self.mac})'
            )
        return "Unknown device"

    def set_mac(self, value):
        """Set device mac."""
        if value in ("WoHand", "WoMeter", SERVICE_UUID):
            self.mac = self.device.addr

    def set_service_data(self, value):
        """Extract service data"""
        if len(value) != 16:
            return
        hexv = binascii.unhexlify(value)
        value = bytes.fromhex(value)
        temperature = (value[6] & 0b01111111) + (
            (value[5] & 0b00001111) / 10
        )  # Absolute value of temp
        if not (value[6] & 0b10000000):  # Is temp negative?
            temperature = -temperature
        if not (value[7] & 0b10000000):  # C or F?
            temp_scale = "C"
        else:
            temp_scale = "F"
            temperature = temperature * 1.8 + 32  # Convert to F
        humidity = value[7] & 0b01111111
        self.data = dict(
            model=hexv[2:3].decode(),
            mode=hexv[3:4].hex(),
            date=datetime.datetime.now(),
            temp=float(temperature),
            temp_scale=temp_scale,
            humidity=hexv[7],
        )
        print(self.data)
