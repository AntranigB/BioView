from bioview.datatypes import Configuration


class AfgConfiguration(Configuration):
    def __init__(
        self,
        device_name: str = "AFG2021",
        resource_name: str = "",  # VISA address; empty means auto-discover over USB
        channel: int = 1,
        shape: str = "SINusoid",
        frequency: float = 1e3,  # Hz
        amplitude: float = 1.0,  # Vpp
        offset: float = 0.0,  # V
        load: str = "50",  # ohms, or "INFinity" for high-Z
        output_on_start: bool = True,
        frequency_steps: list = [],  # Optional list of frequencies (Hz) to step through while running
        step_dwell: float = 1.0,  # Seconds spent at each step
        loop_steps: bool = False,
        timeout_ms: int = 5000,
        visa_backend: str = "",  # "" = default VISA, "@py" = pyvisa-py
    ):
        super().__init__()

        self.device_name = device_name
        self.resource_name = resource_name
        self.channel = channel
        self.shape = shape
        self.frequency = frequency
        self.amplitude = amplitude
        self.offset = offset
        self.load = load
        self.output_on_start = output_on_start
        self.frequency_steps = list(frequency_steps)
        self.step_dwell = step_dwell
        self.loop_steps = loop_steps
        self.timeout_ms = timeout_ms
        self.visa_backend = visa_backend

    def get_disp_freq(self):
        return 1
