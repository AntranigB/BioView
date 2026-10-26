import queue
import sys
import time
import types

# bioview.listeners imports uhd at package import time; it is Windows-only on PyPI
sys.modules.setdefault("uhd", types.ModuleType("uhd"))

import pytest

from bioview.datatypes import ConnectionStatus, ResponseType
from bioview.device import get_device_object
from bioview.device.afg import AfgConfiguration, AfgDevice, AfgDriver, AfgError


class FakeVisa:
    """Records writes and answers the few queries the driver makes."""

    def __init__(self, idn="TEKTRONIX,AFG2021,C000001,SCPI:99.0 FV:1.0.0", errors=()):
        self.idn = idn
        self.writes = []
        self.errors = list(errors)
        self.closed = False

    def write(self, cmd):
        self.writes.append(cmd)

    def query(self, cmd):
        if cmd == "*IDN?":
            return self.idn + "\n"
        if cmd == "SYSTem:ERRor?":
            return self.errors.pop(0) if self.errors else '0,"No error"'
        if cmd == "OUTPut1:STATe?":
            on = [w for w in self.writes if w.startswith("OUTPut1:STATe")]
            return "1" if on and on[-1].endswith("ON") else "0"
        raise AssertionError(cmd)

    def close(self):
        self.closed = True


def make_device(fake=None, **cfg):
    fake = fake or FakeVisa()
    config = AfgConfiguration(**cfg)
    driver = AfgDriver(resource=fake, channel=config.channel)
    dev = AfgDevice("afg", config, queue.Queue(), queue.Queue(), driver=driver)
    return dev, fake


def statuses(dev):
    out = []
    while not dev.resp_queue.empty():
        m = dev.resp_queue.get_nowait()
        if m.msg_type == ResponseType.STATUS:
            out.append(m.value[1])
    return out


def test_driver_commands_match_manual_syntax():
    fake = FakeVisa()
    drv = AfgDriver(resource=fake)
    assert "AFG2021" in drv.open()
    drv.configure("sin", 1.5e6, 0.8, 0.1, "INF")
    drv.set_output(True)
    assert fake.writes == [
        "OUTPut1:IMPedance INFinity",
        "SOURce1:FUNCtion:SHAPe SINusoid",
        "SOURce1:FREQuency:FIXed 1500000",
        "SOURce1:VOLTage:UNIT VPP",
        "SOURce1:VOLTage:LEVel:IMMediate:AMPLitude 0.8",
        "SOURce1:VOLTage:LEVel:IMMediate:OFFSet 0.1",
        "OUTPut1:STATe ON",
    ]
    assert drv.get_output() is True


def test_driver_rejects_other_instruments():
    drv = AfgDriver(resource=FakeVisa(idn="KEYSIGHT,34461A,1,1"))
    with pytest.raises(AfgError):
        drv.open()


def test_driver_raises_on_instrument_error():
    drv = AfgDriver(resource=FakeVisa(errors=['-222,"Data out of range"']))
    drv.open()
    with pytest.raises(AfgError, match="Data out of range"):
        drv.configure("SIN", 1e3, 1, 0, 50)


def test_factory_returns_afg_device():
    dev = get_device_object(
        "afg", AfgConfiguration(), queue.Queue(), queue.Queue(), False,
        types.SimpleNamespace(get_save_path=lambda n: None),
    )
    assert isinstance(dev, AfgDevice)
    assert dev.data_sources == []


def test_connect_run_stop_disconnect():
    dev, fake = make_device(frequency=2e6)
    dev.connect()
    assert statuses(dev)[-1] == ConnectionStatus.CONNECTED
    assert fake.writes[-1] == "OUTPut1:STATe OFF"  # safe until run

    dev.run()
    assert fake.writes[-1] == "OUTPut1:STATe ON"
    dev.stop()
    assert fake.writes[-1] == "OUTPut1:STATe OFF"

    dev.disconnect()
    assert fake.closed
    assert statuses(dev)[-1] == ConnectionStatus.DISCONNECTED


def test_connect_failure_reports_disconnected():
    dev, _ = make_device(fake=FakeVisa(idn="OTHER,THING,1,1"))
    dev.connect()
    assert statuses(dev)[-1] == ConnectionStatus.DISCONNECTED
    assert dev.handler is None


def test_live_parameter_update():
    dev, fake = make_device()
    dev.connect()
    dev.update_config("frequency", 5e3)
    assert fake.writes[-1] == "SOURce1:FREQuency:FIXed 5000"
    assert dev.config.frequency == 5e3


def test_frequency_steps():
    dev, fake = make_device(frequency_steps=[1e3, 2e3, 3e3], step_dwell=0.05)
    dev.connect()
    dev.run()
    time.sleep(0.4)
    dev.stop()
    freqs = [w for w in fake.writes if w.startswith("SOURce1:FREQuency:FIXed")]
    assert freqs[-3:] == [f"SOURce1:FREQuency:FIXed {f}" for f in (1000, 2000, 3000)]
