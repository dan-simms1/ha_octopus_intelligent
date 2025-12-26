import pytest

from custom_components.octopus_intelligent.binary_sensor import (
    SLOT_MODE_OFFPEAK,
    SLOT_MODE_SMART_CHARGE,
    _is_slot_mode_active,
)


class DummySystem:
    def __init__(self, *, smart_charge=False, offpeak=False, device_offpeak=False):
        self.smart_charge = smart_charge
        self.offpeak = offpeak
        self.device_offpeak = device_offpeak
        self.calls: list[tuple] = []

    def is_off_peak_charging_now(self, *, minutes_offset: int = 0, device_id: str | None = None):
        self.calls.append(("charging", minutes_offset, device_id))
        return self.smart_charge

    def is_off_peak_time_now(self, minutes_offset: int = 0):
        self.calls.append(("offpeak", minutes_offset))
        return self.offpeak

    def is_device_off_peak_window_now(self, device_id: str | None, minutes_offset: int = 0):
        self.calls.append(("device_offpeak", minutes_offset, device_id))
        return self.device_offpeak


def test_smart_charge_mode_uses_dispatch_calls():
    system = DummySystem(smart_charge=True)

    assert _is_slot_mode_active(system, SLOT_MODE_SMART_CHARGE, "vehicle-1", 30)
    assert system.calls == [("charging", 30, "vehicle-1")]


def test_combined_offpeak_uses_tariff_window():
    system = DummySystem(offpeak=True)

    assert _is_slot_mode_active(system, SLOT_MODE_OFFPEAK, None, 0)
    assert system.calls == [("offpeak", 0)]


def test_device_offpeak_respects_device_helper():
    system = DummySystem(device_offpeak=True)

    assert _is_slot_mode_active(system, SLOT_MODE_OFFPEAK, "vehicle-2", 60)
    assert system.calls == [("device_offpeak", 60, "vehicle-2")]
