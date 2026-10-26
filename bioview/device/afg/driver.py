"""Thin SCPI driver for the Tektronix AFG2021 (and other AFG1000/2000-series) function generators.

Commands follow the AFG2021 Programmer Manual (077-0587-01). The instrument is
reached over USB-TMC through PyVISA; a pre-built VISA resource can be injected
for testing.
"""

SHAPES = {
    "SIN": "SINusoid",
    "SINUSOID": "SINusoid",
    "SQU": "SQUare",
    "SQUARE": "SQUare",
    "PULS": "PULSe",
    "PULSE": "PULSe",
    "RAMP": "RAMP",
    "NOISE": "PRNoise",
    "PRN": "PRNoise",
    "DC": "DC",
}


class AfgError(RuntimeError):
    pass


def _num(value):
    return f"{float(value):.12g}"


def _load(value):
    if isinstance(value, str) and value.upper().startswith("INF"):
        return "INFinity"
    return _num(value)


class AfgDriver:
    def __init__(
        self,
        resource_name: str = "",
        channel: int = 1,
        timeout_ms: int = 5000,
        visa_backend: str = "",
        resource=None,
    ):
        self.resource_name = resource_name
        self.channel = channel
        self.timeout_ms = timeout_ms
        self.visa_backend = visa_backend
        self._inst = resource
        self.idn = ""

    # Connection
    def open(self):
        if self._inst is None:
            self._inst = self._open_visa()

        self._inst.timeout = self.timeout_ms
        self._inst.write_termination = "\n"
        self._inst.read_termination = "\n"
        self.idn = self.query("*IDN?")
        if "AFG" not in self.idn.upper():
            self.close()
            raise AfgError(f"Unexpected instrument: {self.idn!r}")
        return self.idn

    def _open_visa(self):
        try:
            import pyvisa
        except ImportError as e:
            raise AfgError(
                "pyvisa is required for the AFG module: pip install pyvisa pyvisa-py pyusb"
            ) from e

        rm = pyvisa.ResourceManager(self.visa_backend)
        name = self.resource_name or self._find_resource(rm)
        return rm.open_resource(name)

    @staticmethod
    def _find_resource(rm):
        # Tektronix USB-TMC resources look like USB0::0x0699::0x....::<serial>::INSTR
        for name in rm.list_resources("USB?*INSTR"):
            if "0x0699" not in name.lower():
                continue
            try:
                inst = rm.open_resource(name)
                idn = inst.query("*IDN?")
                inst.close()
            except Exception:
                continue
            if "AFG" in idn.upper():
                return name
        raise AfgError("No Tektronix AFG found over USB. Pass resource_name explicitly.")

    def close(self):
        if self._inst is not None:
            try:
                self._inst.close()
            finally:
                self._inst = None

    @property
    def is_open(self):
        return self._inst is not None

    # Low-level I/O
    def write(self, cmd: str):
        self._inst.write(cmd)

    def query(self, cmd: str) -> str:
        return str(self._inst.query(cmd)).strip()

    def check_errors(self):
        """Drain the error queue and raise if anything was reported."""
        errors = []
        for _ in range(20):
            resp = self.query("SYSTem:ERRor?")
            if resp.startswith("0"):
                break
            errors.append(resp)
        if errors:
            raise AfgError("; ".join(errors))

    # Settings
    def reset(self):
        self.write("*RST")

    def set_shape(self, shape: str):
        key = str(shape).upper()
        self.write(f"SOURce{self.channel}:FUNCtion:SHAPe {SHAPES.get(key, shape)}")

    def set_frequency(self, hz: float):
        self.write(f"SOURce{self.channel}:FREQuency:FIXed {_num(hz)}")

    def set_amplitude(self, vpp: float):
        self.write(f"SOURce{self.channel}:VOLTage:UNIT VPP")
        self.write(f"SOURce{self.channel}:VOLTage:LEVel:IMMediate:AMPLitude {_num(vpp)}")

    def set_offset(self, volts: float):
        self.write(f"SOURce{self.channel}:VOLTage:LEVel:IMMediate:OFFSet {_num(volts)}")

    def set_load(self, ohms):
        self.write(f"OUTPut{self.channel}:IMPedance {_load(ohms)}")

    def set_output(self, on: bool):
        self.write(f"OUTPut{self.channel}:STATe {'ON' if on else 'OFF'}")

    def get_output(self) -> bool:
        return self.query(f"OUTPut{self.channel}:STATe?") in ("1", "ON")

    def get_frequency(self) -> float:
        return float(self.query(f"SOURce{self.channel}:FREQuency:FIXed?"))

    def configure(self, shape, frequency, amplitude, offset, load):
        # Load first: amplitude/offset are interpreted relative to it
        self.set_load(load)
        self.set_shape(shape)
        self.set_frequency(frequency)
        self.set_amplitude(amplitude)
        self.set_offset(offset)
        self.check_errors()
