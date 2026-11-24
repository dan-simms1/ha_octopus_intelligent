"""v2.2.4: when Octopus fails for one device (KT-CT-4340 "Unable to fetch
planned dispatches", seen intermittently after a second car was
registered), the other devices keep updating and the failed one keeps its
last data for up to 30 minutes instead of the whole integration going
unavailable."""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from importlib import util as importlib_util
from pathlib import Path
from types import ModuleType

import pytest

import test_util  # noqa: F401  (sets up the package and const/util modules)

PKG = "custom_components.octopus_intelligent"
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "octopus_intelligent"
util = sys.modules[f"{PKG}.util"] if f"{PKG}.util" in sys.modules else test_util.util_module
NOW = datetime(2026, 11, 24, 17, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------ the helper
def state(planned_ends):
    return {"device": {"id": "d1"}, "preferences": {}, "status": {},
            "plannedDispatches": [{"startDtUtc": "2026-11-24 16:00:00+0000", "endDtUtc": e} for e in planned_ends],
            "completedDispatches": [{"startDtUtc": "2026-11-24 12:00:00+0000"}]}


def test_recent_data_stands_in_and_ended_slots_are_dropped():
    kept = util.reuse_stale_device_state(
        state(["2026-11-24 16:30:00+0000", "2026-11-24 17:30:00+0000"]), NOW - timedelta(minutes=10), NOW)
    assert [d["endDtUtc"] for d in kept["plannedDispatches"]] == ["2026-11-24 17:30:00+0000"]
    assert kept["completedDispatches"] and kept["stale_since"] == (NOW - timedelta(minutes=10)).isoformat()


@pytest.mark.parametrize("prev,last_ok", [(None, NOW), (state([]), None), (state([]), NOW - timedelta(minutes=31))])
def test_nothing_recent_is_none(prev, last_ok):
    assert util.reuse_stale_device_state(prev, last_ok, NOW) is None


def test_time_formats():
    assert util._parse_dispatch_time("2026-11-24T17:30:00Z") == datetime(2026, 11, 24, 17, 30, tzinfo=timezone.utc)
    assert util._parse_dispatch_time("junk") is None


# ------------------------------------------------------------ the update loop
def _stub(name, **attrs):
    m = ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class UpdateFailed(Exception):
    pass


class DataUpdateCoordinator:
    def __init__(self, *a, **k):
        self.data = None


def load_system():
    _stub("homeassistant")
    _stub("homeassistant.util")
    _stub("homeassistant.util.dt", utcnow=lambda: NOW)
    sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]
    _stub("homeassistant.helpers")
    _stub("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=DataUpdateCoordinator, UpdateFailed=UpdateFailed)
    _stub(f"{PKG}.graphql_client", OctopusEnergyGraphQLClient=lambda key: None)
    _stub(f"{PKG}.graphql_util", validate_octopus_account=lambda *a: None)
    _stub(f"{PKG}.persistent_data", PersistentData=lambda: type("P", (), {
        "last_seen_planned_dispatch_sources": {}, "last_seen_planned_dispatch_source": ""})(),
        PersistentDataStore=lambda *a: None)
    spec = importlib_util.spec_from_file_location(f"{PKG}.octopus_intelligent_system", ROOT / "octopus_intelligent_system.py")
    mod = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Client:
    def __init__(self, fail):
        self.fail = set(fail)

    async def async_get_devices(self, account):
        return [{"id": d, "deviceType": "ELECTRIC_VEHICLES", "provider": "TESLA", "status": {}} for d in ("y", "m3")]

    async def async_get_device_preferences(self, account, device_id):
        return {}

    async def async_get_device_dispatches(self, account, device_id):
        if device_id in self.fail:
            raise RuntimeError("Unable to fetch planned dispatches. KT-CT-4340")
        return {"flexPlannedDispatches": [{"start": "2026-11-24T18:00:00Z", "end": "2026-11-24T18:30:00Z",
                                           "type": "SMART", "energyAddedKwh": -2.0}],
                "completedDispatches": []}


def system(fail=()):
    mod = load_system()
    s = mod.OctopusIntelligentSystem.__new__(mod.OctopusIntelligentSystem)
    DataUpdateCoordinator.__init__(s)
    s._account_id = "A-1"
    s._primary_equipment_id = None
    s._device_last_ok = {}
    s._persistent_data = mod.PersistentData()
    s.client = Client(fail)
    return s


def run(s):
    return asyncio.run(s._async_update_data())


def test_one_device_failing_keeps_the_other_and_its_last_data():
    s = system()
    s.data = run(s)
    assert set(s.data["devices"]) == {"y", "m3"}
    s.client.fail = {"m3"}
    data = run(s)
    assert set(data["devices"]) == {"y", "m3"}
    assert data["devices"]["m3"]["stale_since"] == NOW.isoformat()
    assert len(data["plannedDispatches"]) == 2


def test_a_failing_device_with_no_recent_data_is_left_out():
    s = system(fail={"m3"})
    data = run(s)
    assert set(data["devices"]) == {"y"}


def test_every_device_failing_with_nothing_held_fails_the_update():
    s = system(fail={"m3", "y"})
    with pytest.raises(UpdateFailed):
        run(s)
