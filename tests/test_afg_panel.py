import sys
import types

sys.modules.setdefault("uhd", types.ModuleType("uhd"))

import pytest
from PyQt6.QtWidgets import QApplication

from bioview.device import AfgConfiguration
from bioview.ui import AfgDeviceConfigPanel
from bioview.ui.afg_device_config import parse_frequency_steps


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_parse_frequency_steps():
    assert parse_frequency_steps("100, 110 120.5") == [100e3, 110e3, 120.5e3]
    assert parse_frequency_steps("") == []
    with pytest.raises(ValueError):
        parse_frequency_steps("abc")
    with pytest.raises(ValueError):
        parse_frequency_steps("-5")


def test_panel_shows_config_and_emits_changes(qapp):
    cfg = AfgConfiguration(frequency=2.5e6, amplitude=0.5, shape="SQUare", load="INFinity")
    panel = AfgDeviceConfigPanel(cfg)
    changes, logs = [], []
    panel.paramChanged.connect(lambda p, v: changes.append((p, v)))
    panel.logEvent.connect(lambda lvl, msg: logs.append((lvl, msg)))

    assert panel.freq_box.value() == pytest.approx(2500.0)
    assert panel.shape_box.currentData() == "SQUare"
    assert panel.load_box.currentData() == "INFinity"

    panel.freq_box.setValue(100.0)  # kHz
    assert cfg.frequency == pytest.approx(100e3)
    assert ("frequency", pytest.approx(100e3)) in changes

    panel.shape_box.setCurrentIndex(0)
    assert cfg.shape == "SINusoid"

    panel.steps_edit.setText("10, 20")
    panel.steps_edit.editingFinished.emit()
    assert cfg.frequency_steps == [10e3, 20e3]

    n = len(changes)
    panel.steps_edit.setText("bogus")
    panel.steps_edit.editingFinished.emit()
    assert len(changes) == n  # invalid input is not applied
    assert cfg.frequency_steps == [10e3, 20e3]
    assert logs[-1][0] == "error"


def test_render_screenshot(qapp, tmp_path):
    panel = AfgDeviceConfigPanel(AfgConfiguration(frequency=1e5, frequency_steps=[100e3, 110e3]))
    panel.resize(360, 320)
    assert not panel.grab().isNull()
