from .config import AfgConfiguration
from .device import AfgDevice
from .driver import AfgDriver, AfgError


def get_device_object(
    device_name, config, resp_queue, data_queue, save=False, save_path=None
):
    return AfgDevice(
        device_name=device_name,
        config=config,
        resp_queue=resp_queue,
        data_queue=data_queue,
        save=save,
        save_path=save_path,
    )


def discover_devices():
    devices = []

    try:
        import pyvisa

        rm = pyvisa.ResourceManager()
        for name in rm.list_resources("USB?*INSTR"):
            if "0x0699" not in name.lower():  # Tektronix vendor ID
                continue
            devices.append(
                {"resource_name": name, "handler_type": "afg", "vendor": "Tektronix"}
            )
    except Exception as e:
        print(f"Error occured in VISA device discovery: {e}")

    return devices


__all__ = [
    "AfgConfiguration",
    "AfgDevice",
    "AfgDriver",
    "AfgError",
    "get_device_object",
    "discover_devices",
]
