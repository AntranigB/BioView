import threading

from bioview.datatypes import ConnectionStatus, Device
from bioview.utils import emit_signal

from .config import AfgConfiguration
from .driver import AfgDriver


class AfgDevice(Device):
    """Tektronix AFG function generator acting as a stimulus source.

    It produces no data of its own, so it exposes no data sources. Connect
    opens the USB-TMC session and applies the configuration, run turns the
    output on (and optionally steps through frequencies), and stop turns it off.
    """

    def __init__(
        self,
        device_name,
        config: AfgConfiguration,
        resp_queue,
        data_queue,
        save=False,
        save_path=None,
        display=False,
        driver=None,
    ):
        super().__init__(
            device_name=device_name,
            config=config,
            resp_queue=resp_queue,
            data_queue=data_queue,
            device_type="afg",
            save=save,
            save_path=save_path,
            display=display,
        )
        self.handler = driver  # Injectable for testing
        self._step_thread = None
        self._stop_event = threading.Event()

    def _populate_data_sources(self):
        pass  # A function generator has nothing to plot or save

    def connect(self):
        self.connection_state_changed(ConnectionStatus.CONNECTING)
        try:
            if self.handler is None:
                self.handler = AfgDriver(
                    resource_name=self.config.resource_name,
                    channel=self.config.channel,
                    timeout_ms=self.config.timeout_ms,
                    visa_backend=self.config.visa_backend,
                )
            idn = self.handler.open()
            self._apply_config()
            self.handler.set_output(False)  # Never start emitting until run
            self.log_event("info", f"Connected to {idn}")
            self._on_connect_success()
            self.state = ConnectionStatus.CONNECTED
        except Exception as e:
            self.handler = None
            self._on_connect_failure(f"Unable to initialize AFG: {e}")

    def run(self):
        if self.handler is None or not self.handler.is_open:
            self.log_event("error", "AFG is not connected")
            return

        try:
            self._apply_config()
            if self.config.output_on_start:
                self.handler.set_output(True)
        except Exception as e:
            self.log_event("error", f"AFG failed to start: {e}")
            return

        steps = list(self.config.frequency_steps)
        if steps:
            self._stop_event.clear()
            self._step_thread = threading.Thread(
                target=self._step_frequencies, args=(steps,), daemon=True
            )
            self._step_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._step_thread is not None:
            self._step_thread.join(timeout=2 * self.config.step_dwell + 1)
            self._step_thread = None

        if self.handler is not None and self.handler.is_open:
            try:
                self.handler.set_output(False)
            except Exception as e:
                self.log_event("error", f"AFG failed to stop output: {e}")

    def disconnect(self):
        self.stop()
        if self.handler is not None:
            try:
                self.handler.close()
            except Exception:
                pass
            self.handler = None
        super().disconnect()
        emit_signal(self.connection_state_changed, ConnectionStatus.DISCONNECTED)

    def update_config(self, param, value):
        """Update a setting and, if connected, push it to the instrument immediately."""
        super().update_config(param, value)
        if self.handler is None or not self.handler.is_open:
            return

        try:
            if param == "frequency":
                self.handler.set_frequency(self.config.frequency)
            elif param == "amplitude":
                self.handler.set_amplitude(self.config.amplitude)
            elif param == "offset":
                self.handler.set_offset(self.config.offset)
            elif param == "shape":
                self.handler.set_shape(self.config.shape)
            elif param == "load":
                self.handler.set_load(self.config.load)
        except Exception as e:
            self.log_event("error", f"AFG failed to update {param}: {e}")

    def _apply_config(self):
        cfg = self.config
        self.handler.configure(
            shape=cfg.shape,
            frequency=cfg.frequency,
            amplitude=cfg.amplitude,
            offset=cfg.offset,
            load=cfg.load,
        )

    def _step_frequencies(self, steps):
        while not self._stop_event.is_set():
            for freq in steps:
                if self._stop_event.is_set():
                    return
                try:
                    self.handler.set_frequency(freq)
                    self.config.frequency = freq
                except Exception as e:
                    self.log_event("error", f"AFG frequency step failed: {e}")
                    return
                self.log_event("info", f"AFG frequency set to {freq:g} Hz")
                if self._stop_event.wait(self.config.step_dwell):
                    return
            if not self.config.loop_steps:
                return
