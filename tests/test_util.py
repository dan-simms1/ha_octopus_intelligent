from datetime import timedelta
from importlib import util as importlib_util
from pathlib import Path
import sys
from types import ModuleType

COMPONENT_ROOT = Path(__file__).resolve().parents[1] / "custom_components"
PACKAGE_PATH = COMPONENT_ROOT / "octopus_intelligent"
PACKAGE_NAME = "custom_components.octopus_intelligent"

if "custom_components" not in sys.modules:
    custom_components_pkg = ModuleType("custom_components")
    custom_components_pkg.__path__ = [str(COMPONENT_ROOT)]
    sys.modules["custom_components"] = custom_components_pkg

if PACKAGE_NAME not in sys.modules:
    octopus_pkg = ModuleType(PACKAGE_NAME)
    octopus_pkg.__path__ = [str(PACKAGE_PATH)]
    sys.modules[PACKAGE_NAME] = octopus_pkg

const_spec = importlib_util.spec_from_file_location(
    f"{PACKAGE_NAME}.const", PACKAGE_PATH / "const.py"
)
const_module = importlib_util.module_from_spec(const_spec)
const_spec.loader.exec_module(const_module)  # type: ignore[attr-defined]
sys.modules[f"{PACKAGE_NAME}.const"] = const_module

util_spec = importlib_util.spec_from_file_location(
    f"{PACKAGE_NAME}.util", PACKAGE_PATH / "util.py"
)
util_module = importlib_util.module_from_spec(util_spec)
util_spec.loader.exec_module(util_module)  # type: ignore[attr-defined]

to_timedelta = util_module.to_timedelta
to_hours_after_midnight = util_module.to_hours_after_midnight


def test_to_timedelta_accepts_seconds():
    delta = to_timedelta("04:05:30")

    assert delta == timedelta(hours=4, minutes=5, seconds=30)


def test_to_hours_after_midnight_handles_seconds():
    hours = to_hours_after_midnight("06:30:00")

    assert hours == 6.5
