"""Tests for data_processing_service: CC-SI mapping and municipality normalization."""

import pandas as pd

from app.api import data as data_api
from app.services.data_processing_service import _CC_SI_PREFIX_MAP, enrich_training_df, group_property_type
from app.utils.slovenian_labels import format_municipality_label


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


def test_enrich_training_df_preserves_display_names_and_adds_normalized_column():
    df = pd.DataFrame(
        {
            "municipality": ["Škofja   Loka", "Ljubljana"],
            "property_type": ["Stanovanje", "Hiša"],
            "size_m2": [55, 120],
        }
    )

    enriched = enrich_training_df(df)

    assert enriched["municipality"].tolist() == ["Škofja Loka", "Ljubljana"]
    assert enriched["municipality_normalized"].tolist() == ["skofja loka", "ljubljana"]


def test_format_municipality_label_handles_ascii_and_hyphenated_names():
    assert format_municipality_label("skofja loka") == "Škofja Loka"
    assert format_municipality_label("race-fram") == "Rače - Fram"


def test_format_municipality_label_canonicalizes_aliases_and_unknowns():
    assert format_municipality_label("sv. trojica v slov. goricah") == "Sveta Trojica v Slovenskih goricah"
    assert format_municipality_label("kanal") == "Kanal ob Soči"
    assert format_municipality_label("sucna vas") is None


def test_build_quality_summary_uses_canonical_municipalities_and_tracks_unresolved_rows(tmp_path, monkeypatch):
    csv_path = tmp_path / "train.csv"
    pd.DataFrame(
        {
            "municipality": [
                "Ljubljana",
                "unknown",
                "kanal",
                "Kanal ob Soči",
                "sv. trojica v slov. goricah",
                "Sveta Trojica v Slovenskih goricah",
            ]
        }
    ).to_csv(csv_path, index=False)

    monkeypatch.setattr(data_api, "TRAIN_CSV", str(csv_path))

    summary = data_api._build_quality_summary()

    assert summary["training_dataset_exists"] is True
    assert summary["covered_municipalities"] == 3
    assert summary["unresolved_rows"] == 1
    assert summary["unresolved_labels"][0]["label"] == "unknown"
    assert summary["unresolved_labels"][0]["count"] == 1
    assert summary["alias_collisions"][0]["canonical"] in {
        "Kanal ob Soči",
        "Sveta Trojica v Slovenskih goricah",
    }
