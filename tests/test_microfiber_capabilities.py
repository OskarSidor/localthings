"""Microfiber laundry-lint filter appliance (issue #475,
AMF-WW-TP1-22-COMMON). Reports the washer resource surface -- washer
course/settings, job-beginning status, operational state -- so it shares
the washer registry (routed via /oic/d's x.com.st.d.microfiberfilter),
plus its own filter resources: a water/microfiber filter usage counter and
a separate /filterstatus/vs/0 blockage notice.
"""

from custom_components.localthings.registry.adapter import flatten
from custom_components.localthings.registry.by_type import for_device_by_oic_type, resolve
from custom_components.localthings.registry.capabilities import common
from custom_components.localthings.registry.discovery import discover
from custom_components.localthings.registry.entities import BinarySensorDesc
from tests.conftest import _load_device

FIXTURE = "microfiber"
DEVICE_TYPES = ("oic.wk.d", "x.com.st.d.microfiberfilter")


def _device():
    resources = _load_device(FIXTURE)
    reg = resolve(resources, device_types=DEVICE_TYPES)
    return reg, resources


def _state():
    reg, resources = _device()
    bound = discover(resources, reg.capabilities, reg.pattern_capabilities)
    return flatten(bound, resources)


def test_routes_to_washer_via_oic_type():
    reg = for_device_by_oic_type(DEVICE_TYPES)
    assert reg is not None and reg.name == "washer"


def test_no_unbound_hrefs():
    reg, resources = _device()
    unbound = []
    discover(resources, reg.capabilities, reg.pattern_capabilities, log=unbound.append)
    assert unbound == []


def test_water_filter_usage_and_status_bound():
    state = _state()
    assert state["filter_usage"] == "4"
    assert state["filter_status"] == "normal"


def test_filter_blockage_is_a_problem_binary_sensor():
    """/filterstatus/vs/0's filterStatusNotice is a bare (non-`x.com...`)
    field; 'Normal' here reads as no problem."""
    desc = next(e for e in common.FILTER_STATUS.entities if e.key == "filter_blockage")
    assert isinstance(desc, BinarySensorDesc)
    assert desc.device_class == "problem"
    assert desc.value_fn("Blockage") is True
    assert desc.value_fn("Normal") is False
    assert _state()["filter_blockage"] is False


def test_filter_reset_button_offered():
    """The AMF filter declares filterResetType ['replaceable'], so the
    shared reset button applies here too (read-only listing until a
    reporter confirms the write on hardware)."""
    reg, resources = _device()
    bound = discover(resources, reg.capabilities, reg.pattern_capabilities)
    state = flatten(bound, resources)
    # Reset is a stateless button, so it doesn't appear in flattened state;
    # assert the descriptor exists and its gate passes on this rep.
    reset = next(e for e in common.WATER_FILTER.entities if e.key == "filter_reset")
    assert reset.exists_fn is not None
    assert reset.exists_fn(resources["/filter/waterfilter/vs/0"], resources)
    assert "filter_usage" in state
