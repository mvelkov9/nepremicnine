"""Tests for data_processing_service: CC-SI mapping and group_property_type."""

from app.services.data_processing_service import _CC_SI_PREFIX_MAP, group_property_type


def test_cc_si_prefix_map_1110_is_hisa():
    assert _CC_SI_PREFIX_MAP["1110"] == "hisa"


def test_cc_si_prefix_map_1122_is_stanovanje():
    assert _CC_SI_PREFIX_MAP["1122"] == "stanovanje"


def test_cc_si_prefix_map_1200_exists():
    """All 9 new CC-SI codes should be present in the map."""
    expected_codes = ["1200", "1241", "1262", "1263", "1264", "1265", "1272", "1280", "1290"]
    for code in expected_codes:
        assert code in _CC_SI_PREFIX_MAP, f"CC-SI code {code} missing from map"


def test_group_property_type_with_ccsi_code():
    """group_property_type should resolve a CC-SI code via the prefix map."""
    assert group_property_type("1122") == "stanovanje"
    assert group_property_type("1110") == "hisa"
    assert group_property_type("1242") == "garaza"
