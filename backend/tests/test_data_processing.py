"""Tests for data_processing_service: CC-SI mapping and municipality normalization."""

import pandas as pd
import pytest

from app.api import data as data_api
from app.services.data_processing_service import (
    _CC_SI_PREFIX_MAP,
    _parse_fractional_numeric_series,
    build_training_df_from_etn_kpp,
    build_training_df_from_etn_kpp_land,
    enrich_training_df,
    group_property_type,
    load_training_metadata,
    prepare_training_csv,
)
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


def test_build_training_df_from_etn_kpp_extracts_requested_share_and_phase_features():
    posli_df = pd.DataFrame(
        {
            "ID_POSLA": ["100"],
            "POGODBENA_CENA_ODSKODNINA": [240000],
            "TRZNOST_POSLA": [1],
            "VRSTA_KUPOPRODAJNEGA_POSLA": [1],
            "STOPNJA_DDV": [22],
            "IME_OBCINE": ["Ljubljana"],
        }
    )
    deli_df = pd.DataFrame(
        {
            "ID_POSLA": ["100"],
            "ID_DELA_STAVBE": ["77"],
            "IME_KO": ["Moste"],
            "NASELJE": ["Ljubljana"],
            "PRODANA_POVRSINA": [80],
            "STEVILO_SOB": [3],
            "VRSTA_DELA_STAVBE": ["stanovanje v večstanovanjski stavbi"],
            "EVIDENTIRANOST_DELA_STAVBE": [1],
            "ATRIJ": [1],
            "DEJANSKA_RABA_DELA_STAVBE": [2],
            "PRODANI_DELEZ_DELA_STAVBE": [0.5],
            "GRADBENA_FAZA": [4],
        }
    )
    zemljisca_df = pd.DataFrame(
        {
            "ID_POSLA": ["100", "100"],
            "POVRSINA_PARCELE": [50, 150],
            "PRODANI_DELEZ_PARCELE": [0.5, 1.0],
            "VRSTA_ZEMLJISCA": ["stavbno", "stavbno"],
        }
    )

    training_df, meta = build_training_df_from_etn_kpp(posli_df, deli_df, zemljisca_df)

    row = training_df.iloc[0]
    assert meta["filter_stats"]["stages"][0]["stage"] == "building_merged_rows"
    assert row["ime_ko"] == "Moste"
    assert row["naselje"] == "Ljubljana"
    assert row["vrsta_dela_stavbe"] == "stanovanje v večstanovanjski stavbi"
    assert row["evidentiranost_dela_stavbe"] == pytest.approx(1.0)
    assert row["atrij"] == pytest.approx(1.0)
    assert row["stopnja_ddv"] == pytest.approx(22.0)
    assert row["vrsta_kupoprodajnega_posla"] == "1"
    assert row["vrsta_zemljisca"] == "stavbno"
    assert row["prodani_delez_dela_stavbe"] == pytest.approx(0.5)
    assert row["gradbena_faza"] == pytest.approx(4.0)
    assert row["prodani_delez_parcele"] == pytest.approx(0.875)


def test_parse_fractional_numeric_series_handles_etn_share_formats():
    parsed = _parse_fractional_numeric_series(
        pd.Series(["1/2", "147/10000", "1", "3,5", "bad", None, "4/0"])
    )

    assert parsed.iloc[0] == pytest.approx(0.5)
    assert parsed.iloc[1] == pytest.approx(0.0147)
    assert parsed.iloc[2] == pytest.approx(1.0)
    assert parsed.iloc[3] == pytest.approx(3.5)
    assert pd.isna(parsed.iloc[4])
    assert pd.isna(parsed.iloc[5])
    assert pd.isna(parsed.iloc[6])


def test_build_training_df_from_etn_kpp_parses_fractional_shares_from_raw_etn():
    posli_df = pd.DataFrame(
        {
            "ID_POSLA": ["200"],
            "POGODBENA_CENA_ODSKODNINA": [180000],
            "TRZNOST_POSLA": [1],
            "VRSTA_KUPOPRODAJNEGA_POSLA": [1],
            "IME_OBCINE": ["Kranj"],
        }
    )
    deli_df = pd.DataFrame(
        {
            "ID_POSLA": ["200"],
            "ID_DELA_STAVBE": ["88"],
            "PRODANA_POVRSINA": [60],
            "STEVILO_SOB": [2],
            "DEJANSKA_RABA_DELA_STAVBE": [2],
            "PRODANI_DELEZ_DELA_STAVBE": ["147/10000"],
            "GRADBENA_FAZA": ["5.0"],
        }
    )
    zemljisca_df = pd.DataFrame(
        {
            "ID_POSLA": ["200", "200"],
            "POVRSINA_PARCELE": [100, 50],
            "PRODANI_DELEZ_PARCELE": ["1/2", "1/4"],
        }
    )

    training_df, _meta = build_training_df_from_etn_kpp(posli_df, deli_df, zemljisca_df)

    row = training_df.iloc[0]
    assert row["prodani_delez_dela_stavbe"] == pytest.approx(0.0147)
    assert row["gradbena_faza"] == pytest.approx(5.0)
    assert row["prodani_delez_parcele"] == pytest.approx((100 * 0.5 + 50 * 0.25) / 150)


def test_build_training_df_from_etn_kpp_land_creates_parcela_rows_for_land_only_transactions():
    posli_df = pd.DataFrame(
        {
            "ID_POSLA": ["300"],
            "POGODBENA_CENA_ODSKODNINA": [50000],
            "TRZNOST_POSLA": [1],
            "VRSTA_KUPOPRODAJNEGA_POSLA": [1],
            "IME_OBCINE": ["Kranj"],
        }
    )
    zemljisca_df = pd.DataFrame(
        {
            "ID_POSLA": ["300", "300"],
            "IME_KO": ["Kranj", "Kranj"],
            "OBCINA": ["Kranj", "Kranj"],
            "PARCELNA_STEVILKA": ["12/1", "12/2"],
            "VRSTA_ZEMLJISCA": ["7", "7"],
            "PRODANI_DELEZ_PARCELE": ["1/1", "1/2"],
            "POVRSINA_PARCELE": [400, 100],
            "POGODBENA_CENA_PARCELE": [40000, 40000],
            "E_CENTROID": [14.36, 14.37],
            "N_CENTROID": [46.24, 46.25],
        }
    )

    training_df, meta = build_training_df_from_etn_kpp_land(posli_df, zemljisca_df)

    assert meta["used_size_column"] == "POVRSINA_PARCELE"
    assert meta["filter_stats"]["stages"][0]["stage"] == "land_candidates_after_building_exclusion"
    assert set(training_df["property_type"]) == {"parcela"}
    assert len(training_df) == 2
    assert training_df["size_m2"].tolist() == [400, 100]
    assert training_df["parcela_m2"].tolist() == [400, 100]
    assert training_df["price_eur"].tolist() == [40000, 40000]
    assert training_df["vrsta_zemljisca"].tolist() == ["7", "7"]
    assert training_df["prodani_delez_parcele"].tolist() == [1.0, 0.5]


def test_prepare_training_csv_preserves_optional_requested_features(tmp_path):
    source_csv = tmp_path / "source.csv"
    output_csv = tmp_path / "train.csv"

    pd.DataFrame(
        {
            "sqm": [75],
            "rooms_src": [3],
            "built": [2008],
            "floor_src": [2],
            "lat": [46.05],
            "lon": [14.5],
            "muni": ["Ljubljana"],
            "ptype": ["Stanovanje"],
            "price": [250000],
            "share_parcela": [0.6],
            "share_del": [1.0],
            "faza": [5],
        }
    ).to_csv(source_csv, index=False)

    result = prepare_training_csv(
        str(source_csv),
        {
            "sqm": "size_m2",
            "rooms_src": "rooms",
            "built": "year_built",
            "floor_src": "floor",
            "lat": "latitude",
            "lon": "longitude",
            "muni": "municipality",
            "ptype": "property_type",
            "price": "price_eur",
            "share_parcela": "prodani_delez_parcele",
            "share_del": "prodani_delez_dela_stavbe",
            "faza": "gradbena_faza",
        },
        str(output_csv),
    )

    prepared = pd.read_csv(output_csv)
    metadata = load_training_metadata(str(output_csv))

    assert "prodani_delez_parcele" in result["columns"]
    assert "prodani_delez_dela_stavbe" in result["columns"]
    assert metadata is not None
    assert metadata["source"] == "mapped_csv"
    assert "gradbena_faza" in result["columns"]
    assert prepared.loc[0, "prodani_delez_parcele"] == pytest.approx(0.6)
    assert prepared.loc[0, "prodani_delez_dela_stavbe"] == pytest.approx(1.0)
    assert prepared.loc[0, "gradbena_faza"] == pytest.approx(5.0)
