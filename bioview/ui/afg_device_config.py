from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
)

from bioview.device import AfgConfiguration

SHAPES = [
    ("Sine", "SINusoid"),
    ("Square", "SQUare"),
    ("Pulse", "PULSe"),
    ("Ramp", "RAMP"),
    ("Noise", "PRNoise"),
    ("DC", "DC"),
]
LOADS = [("50 Ω", "50"), ("High-Z", "INFinity")]


def parse_frequency_steps(text: str) -> list:
    """Parse a comma/space separated list of kHz values into Hz. Raises ValueError."""
    values = [v for v in text.replace(",", " ").split() if v]
    steps = [float(v) * 1e3 for v in values]
    if any(s <= 0 for s in steps):
        raise ValueError("Frequencies must be positive")
    return steps


class AfgDeviceConfigPanel(QGroupBox):
    """Controls for an AFG function generator.

    Edits the AfgConfiguration in place and emits ``paramChanged(name, value)`` so
    the app can forward the change to the instrument when it is connected.
    """

    paramChanged = pyqtSignal(str, object)
    logEvent = pyqtSignal(str, str)

    def __init__(self, config: AfgConfiguration, parent=None):
        super().__init__(f"{config.get_param('device_name')} Function Generator", parent)
        self.config = config
        self.init_ui()

    def init_ui(self):
        cfg = self.config
        layout = QGridLayout()

        self.shape_box = QComboBox()
        for text, scpi in SHAPES:
            self.shape_box.addItem(text, scpi)
        self.shape_box.setCurrentIndex(self._index_of(self.shape_box, cfg.shape))
        self.shape_box.currentIndexChanged.connect(
            lambda _: self._set("shape", self.shape_box.currentData())
        )

        self.freq_box = self._spin(1e-6, 20e3, 6, 1.0, cfg.frequency / 1e3)
        self.freq_box.valueChanged.connect(lambda v: self._set("frequency", v * 1e3))

        self.amp_box = self._spin(0.001, 20, 3, 0.1, cfg.amplitude)
        self.amp_box.valueChanged.connect(lambda v: self._set("amplitude", v))

        self.offset_box = self._spin(-10, 10, 3, 0.1, cfg.offset)
        self.offset_box.valueChanged.connect(lambda v: self._set("offset", v))

        self.load_box = QComboBox()
        for text, scpi in LOADS:
            self.load_box.addItem(text, scpi)
        self.load_box.setCurrentIndex(self._index_of(self.load_box, str(cfg.load)))
        self.load_box.currentIndexChanged.connect(
            lambda _: self._set("load", self.load_box.currentData())
        )

        self.output_check = QCheckBox("Output on when Start is pressed")
        self.output_check.setChecked(cfg.output_on_start)
        self.output_check.toggled.connect(lambda v: self._set("output_on_start", v))

        self.steps_edit = QLineEdit(
            ", ".join(f"{f / 1e3:g}" for f in cfg.frequency_steps)
        )
        self.steps_edit.setPlaceholderText("e.g. 100, 110, 120")
        self.steps_edit.editingFinished.connect(self._steps_edited)

        self.dwell_box = self._spin(0.01, 3600, 2, 0.5, cfg.step_dwell)
        self.dwell_box.valueChanged.connect(lambda v: self._set("step_dwell", v))

        self.loop_check = QCheckBox("Loop steps")
        self.loop_check.setChecked(cfg.loop_steps)
        self.loop_check.toggled.connect(lambda v: self._set("loop_steps", v))

        rows = [
            ("Waveform", self.shape_box),
            ("Frequency (kHz)", self.freq_box),
            ("Amplitude (Vpp)", self.amp_box),
            ("Offset (V)", self.offset_box),
            ("Load", self.load_box),
        ]
        for row, (label, widget) in enumerate(rows):
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(widget, row, 1)

        row = len(rows)
        layout.addWidget(self.output_check, row, 0, 1, 2)
        layout.addWidget(QLabel("Step list (kHz)"), row + 1, 0)
        layout.addWidget(self.steps_edit, row + 1, 1)
        layout.addWidget(QLabel("Dwell (s)"), row + 2, 0)
        layout.addWidget(self.dwell_box, row + 2, 1)
        layout.addWidget(self.loop_check, row + 3, 0, 1, 2)

        self.setLayout(layout)

    @staticmethod
    def _spin(lo, hi, decimals, step, value):
        box = QDoubleSpinBox()
        box.setRange(lo, hi)
        box.setDecimals(decimals)
        box.setSingleStep(step)
        box.setValue(value)
        return box

    @staticmethod
    def _index_of(box, data):
        for i in range(box.count()):
            if str(box.itemData(i)).upper() == str(data).upper():
                return i
        return 0

    def _steps_edited(self):
        try:
            steps = parse_frequency_steps(self.steps_edit.text())
        except ValueError as e:
            self.logEvent.emit("error", f"{self.config.device_name}: Invalid step list: {e}")
            self.steps_edit.setStyleSheet("border: 1px solid red;")
            return

        self.steps_edit.setStyleSheet("")
        self._set("frequency_steps", steps)

    def _set(self, param, value):
        try:
            self.config.set_param(param, value)
        except Exception as e:
            self.logEvent.emit(
                "error", f"{self.config.device_name}: Updating {param} failed: {e}"
            )
            return

        self.logEvent.emit(
            "debug", f"{self.config.device_name}: Updated {param} to {value}"
        )
        self.paramChanged.emit(param, value)
