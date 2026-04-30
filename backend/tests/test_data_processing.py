"""Tests for data_processing_service: CC-SI mapping and municipality normalization."""

import os

import numpy as np
import pandas as pd
import pytest

from app.api import data as data_api
from app.services import data_processing_service as dps
from app.services.data_processing_service import (
    _CC_SI_PREFIX_MAP,
    _emv_layers_for_row,
    _parse_fractional_numeric_series,
    build_training_df_from_etn_kpp,
    build_training_df_from_etn_kpp_land,
    discover_etn_kpp_year_pairs,
    enrich_training_df,
    group_property_type,
    load_training_metadata,
    prepare_training_csv,
    prepare_training_csv_from_etn_kpp,
    prepare_training_csv_from_etn_kpp_bulk,
    resolve_enrichment_options,
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


def test_emv_layers_for_row_prefers_land_type_specific_layers_for_parcela():
    assert _emv_layers_for_row("parcela", "stavbno") == ["emv_vredn_cone_STZ"]
    assert _emv_layers_for_row("parcela", "7") == ["emv_vredn_cone_STZ"]
    assert _emv_layers_for_row("parcela", "kmetijsko") == ["emv_vredn_cone_KME"]
    assert _emv_layers_for_row("parcela", "gozd") == ["emv_vredn_cone_GOZ"]


def test_emv_layers_for_row_falls_back_to_property_type_mapping_when_land_type_unknown():
    assert _emv_layers_for_row("parcela", "drugo") == [
        "emv_vredn_cone_STZ",
        "emv_vredn_cone_PNB",
        "emv_vredn_cone_PNE",
        "emv_vredn_cone_PNP",
        "emv_vredn_cone_KME",
        "emv_vredn_cone_GOZ",
    ]


def test_resolve_vector_gpkg_path_accepts_extracted_shapefile_zip(tmp_path, monkeypatch):
    zip_path = tmp_path / "KN_SLO_KAT_OBCINE_20260315.zip"
    zip_path.write_bytes(b"zip")
    extract_dir = tmp_path / "unzipped_kn"
    extract_dir.mkdir()
    shp_path = extract_dir / "KN_SLO_KAT_OBCINE_KATASTRSKE_OBCINE_poligon.shp"
    shp_path.write_text("shp")

    monkeypatch.setattr(dps, "_extract_vector_zip_cached", lambda _source_path, _mtime: str(extract_dir))

    resolved = dps._resolve_vector_gpkg_path(str(zip_path), "kat_obcine")

    assert resolved == str(shp_path)


def test_resolve_emv_gpkg_path_accepts_extracted_shapefile_bundle(tmp_path, monkeypatch):
    zip_path = tmp_path / "emv_vredn_cone_17_VSE_2025.zip"
    zip_path.write_bytes(b"zip")
    extract_dir = tmp_path / "unzipped_emv"
    extract_dir.mkdir()
    (extract_dir / "emv_vredn_cone_STA.shp").write_text("shp")
    (extract_dir / "emv_vredn_cone_HIS.shp").write_text("shp")

    monkeypatch.setattr(dps, "_extract_vector_zip_cached", lambda _source_path, _mtime: str(extract_dir))

    resolved = dps._resolve_emv_gpkg_path(str(zip_path))

    assert resolved == str(extract_dir)


def test_discover_gurs_enrichment_sources_handles_prefixless_markers_and_prefers_vector_files(tmp_path):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()

    rn_path = uploads_dir / "RN_009_NASLOVI_register_naslovov_ob_20260322.csv"
    rn_path.write_text("id\n1\n", encoding="utf-8")

    gji_dir = uploads_dir / "KGI_SLO_GJI_VODOVOD_20260321"
    gji_dir.mkdir()
    gji_vector = gji_dir / "KGI_SLO_GJI_VODOVOD_tocke_20260321.gpkg"
    gji_vector.write_text("gpkg", encoding="utf-8")
    gji_csv = gji_dir / "KGI_SLO_GJI_VODOVOD_udelezenci_upr_izv_20260321.csv"
    gji_csv.write_text("csv", encoding="utf-8")

    kn_dir = uploads_dir / "KN_SLO_KAT_OBCINE_20260322"
    kn_dir.mkdir()
    kn_shp = kn_dir / "KN_SLO_KAT_OBCINE_KATASTRSKE_OBCINE_poligon.shp"
    kn_shp.write_text("shp", encoding="utf-8")
    kn_cpg = kn_dir / "KN_SLO_KAT_OBCINE_KATASTRSKE_OBCINE_poligon.cpg"
    kn_cpg.write_text("cpg", encoding="utf-8")

    now = 1_900_000_000
    os.utime(gji_vector, (now, now))
    os.utime(gji_csv, (now + 20, now + 20))
    os.utime(kn_shp, (now, now))
    os.utime(kn_cpg, (now + 20, now + 20))

    discovered = dps.discover_gurs_enrichment_sources(str(uploads_dir))

    assert discovered["rn"].endswith("RN_009_NASLOVI_register_naslovov_ob_20260322.csv")
    assert discovered["gji_vodovod"].endswith("KGI_SLO_GJI_VODOVOD_tocke_20260321.gpkg")
    assert discovered["kn_kat_obcine"].endswith("KN_SLO_KAT_OBCINE_KATASTRSKE_OBCINE_poligon.shp")


def test_resolve_upload_dir_from_csv_path_supports_etn_prefix_variants(tmp_path):
    uploads_root = tmp_path / "uploads"
    uploads_root.mkdir()

    etn_dir = uploads_root / "ETN_009_KPP_20260322"
    etn_dir.mkdir()
    csv_path = etn_dir / "ETN_009_KPP_POSLI_20260322.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")

    resolved = dps._resolve_upload_dir_from_csv_path(str(csv_path))

    assert resolved == str(uploads_root)


def test_resolve_upload_dir_from_csv_path_prefers_uploads_root_for_nested_etn_tree(tmp_path):
    uploads_root = tmp_path / "uploads"
    uploads_root.mkdir()

    etn_group = uploads_root / "ETN"
    etn_group.mkdir()
    etn_year_dir = etn_group / "ETN_SLO_2026_KPP_20260322"
    etn_year_dir.mkdir()
    csv_path = etn_year_dir / "ETN_SLO_2026_KPP_KPP_POSLI_20260322.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")

    resolved = dps._resolve_upload_dir_from_csv_path(str(csv_path))

    assert resolved == str(uploads_root)


def test_discover_etn_kpp_year_pairs_filters_requested_year_window(tmp_path):
    uploads_root = tmp_path / "uploads"
    uploads_root.mkdir()

    for year in (2019, 2020, 2021):
        year_dir = uploads_root / f"ETN_SLO_{year}_KPP_20260322"
        year_dir.mkdir()
        (year_dir / f"ETN_SLO_{year}_KPP_KPP_POSLI_20260322.csv").write_text("id\n1\n", encoding="utf-8")
        (year_dir / f"ETN_SLO_{year}_KPP_KPP_DELISTAVB_20260322.csv").write_text("id\n1\n", encoding="utf-8")
        (year_dir / f"ETN_SLO_{year}_KPP_KPP_ZEMLJISCA_20260322.csv").write_text("id\n1\n", encoding="utf-8")

    pairs = discover_etn_kpp_year_pairs(str(uploads_root), start_year=2020, end_year=2021)

    assert [pair["year"] for pair in pairs] == ["2020", "2021"]
    assert all("2019" not in pair["posli_csv_path"] for pair in pairs)


def test_discover_etn_kpp_year_pairs_accepts_flat_csv_layout(tmp_path):
    uploads_root = tmp_path / "uploads"
    uploads_root.mkdir()

    (uploads_root / "ETN_SLO_2022_KPP_KPP_POSLI_20260322.csv").write_text("id\n1\n", encoding="utf-8")
    (uploads_root / "ETN_SLO_2022_KPP_KPP_DELISTAVB_20260322.csv").write_text("id\n1\n", encoding="utf-8")
    (uploads_root / "ETN_SLO_2022_KPP_KPP_ZEMLJISCA_20260322.csv").write_text("id\n1\n", encoding="utf-8")

    pairs = discover_etn_kpp_year_pairs(str(uploads_root), start_year=2022, end_year=2022)

    assert len(pairs) == 1
    assert pairs[0]["year"] == "2022"


def test_resolve_etn_paths_from_zip_if_needed_autocorrects_sifranti_pair_inputs(tmp_path):
    etn_dir = tmp_path / "ETN_SLO_2026_KPP_20260322"
    etn_dir.mkdir()

    posli = etn_dir / "ETN_SLO_2026_KPP_KPP_POSLI_20260322.csv"
    delistavb = etn_dir / "ETN_SLO_2026_KPP_KPP_DELISTAVB_20260322.csv"
    zemljisca = etn_dir / "ETN_SLO_2026_KPP_KPP_ZEMLJISCA_20260322.csv"
    sifranti = etn_dir / "ETN_SLO_2026_KPP_sifranti_20260322.csv"

    for path in [posli, delistavb, zemljisca, sifranti]:
        path.write_text("id\n1\n", encoding="utf-8")

    resolved_posli, resolved_deli, resolved_zem = dps._resolve_etn_paths_from_zip_if_needed(
        str(sifranti),
        str(sifranti),
        str(sifranti),
        str(tmp_path / "tmp_extract"),
    )

    assert resolved_posli == str(posli)
    assert resolved_deli == str(delistavb)
    assert resolved_zem == str(zemljisca)


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


def test_normalize_house_number_key_strips_spreadsheet_decimal_suffix():
    assert dps._normalize_house_number_key("16.0") == "16"
    assert dps._normalize_house_number_key(27.0) == "27"
    assert dps._normalize_house_number_key("3A") == "3a"


def test_format_municipality_label_canonicalizes_aliases_and_unknowns():
    assert format_municipality_label("sv. trojica v slov. goricah") == "Sveta Trojica v Slovenskih goricah"
    assert format_municipality_label("kanal") == "Kanal ob Soči"
    assert format_municipality_label("Dobrova") == "Dobrova - Polhov Gradec"
    assert format_municipality_label("Dolenje Toplice") == "Dolenjske Toplice"
    assert format_municipality_label("Ljubljana Center") == "Ljubljana"
    assert format_municipality_label("Ljubljana - Vič") == "Ljubljana"
    assert format_municipality_label("Mol") == "Ljubljana"
    assert format_municipality_label("Videm pri Ptuju") == "Videm"
    assert format_municipality_label("Vogrsko") == "Renče - Vogrsko"
    assert format_municipality_label("Borovnic?a") == "Borovnica"
    assert format_municipality_label("Polzepa") == "Polzela"
    assert format_municipality_label("Sveti Jurij") is None
    assert format_municipality_label("Ni Podatka") is None
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


def test_build_quality_summary_excludes_noncanonical_municipalities_from_coverage(tmp_path, monkeypatch):
    csv_path = tmp_path / "train.csv"
    pd.DataFrame(
        {
            "municipality": [
                "Ljubljana",
                "Sveti Jurij",
                "Polzela",
                "Polzepa",
                "Ni Podatka",
            ]
        }
    ).to_csv(csv_path, index=False)

    monkeypatch.setattr(data_api, "TRAIN_CSV", str(csv_path))

    summary = data_api._build_quality_summary()

    assert summary["covered_municipalities"] == 2
    assert summary["unresolved_rows"] == 2
    assert summary["noncanonical_rows"] == 0
    assert summary["noncanonical_labels"] == []
    assert {item["label"] for item in summary["unresolved_labels"]} == {"Sveti Jurij", "Ni Podatka"}
    assert any(item["canonical"] == "Polzela" for item in summary["alias_collisions"])


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


def test_build_training_df_from_etn_kpp_accepts_legacy_trznost_code_4():
    posli_df = pd.DataFrame(
        {
            "ID_POSLA": ["legacy-1"],
            "POGODBENA_CENA_ODSKODNINA": [210000],
            "TRZNOST_POSLA": [4],
            "VRSTA_KUPOPRODAJNEGA_POSLA": [1],
            "IME_OBCINE": ["Ljubljana"],
        }
    )
    deli_df = pd.DataFrame(
        {
            "ID_POSLA": ["legacy-1"],
            "ID_DELA_STAVBE": ["1"],
            "PRODANA_POVRSINA": [72],
            "STEVILO_SOB": [3],
            "DEJANSKA_RABA_DELA_STAVBE": [2],
            "VRSTA_DELA_STAVBE": ["stanovanje"],
        }
    )

    training_df, _meta = build_training_df_from_etn_kpp(posli_df, deli_df)

    assert len(training_df) == 1
    assert training_df.iloc[0]["price_eur"] > 0


def test_build_training_df_from_etn_kpp_coalesces_legacy_area_columns():
    posli_df = pd.DataFrame(
        {
            "ID_POSLA": ["legacy-area-1"],
            "POGODBENA_CENA_ODSKODNINA": [180000],
            "TRZNOST_POSLA": [4],
            "VRSTA_KUPOPRODAJNEGA_POSLA": [1],
            "IME_OBCINE": ["Ljubljana"],
        }
    )
    deli_df = pd.DataFrame(
        {
            "ID_POSLA": ["legacy-area-1"],
            "ID_DELA_STAVBE": ["1"],
            "PRODANA_POVRSINA": [np.nan],
            "PRODANA_POVRSINA_DELA_STAVBE": [68],
            "UPORABNA_POVRSINA": [64],
            "POVRSINA_DELA_STAVBE": [70],
            "STEVILO_SOB": [3],
            "DEJANSKA_RABA_DELA_STAVBE": [2],
            "VRSTA_DELA_STAVBE": ["stanovanje"],
        }
    )

    training_df, meta = build_training_df_from_etn_kpp(posli_df, deli_df)

    assert len(training_df) == 1
    assert training_df.iloc[0]["size_m2"] == pytest.approx(68.0)
    assert meta["used_size_column"] == "PRODANA_POVRSINA_DELA_STAVBE"


def test_parse_fractional_numeric_series_handles_etn_share_formats():
    parsed = _parse_fractional_numeric_series(pd.Series(["1/2", "147/10000", "1", "3,5", "bad", None, "4/0"]))

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


def test_prepare_training_csv_from_etn_kpp_applies_rn_ev_and_emv_enrichment(tmp_path, monkeypatch):
    posli_csv = tmp_path / "ETN_SLO_2026_KPP_KPP_POSLI_20260301.csv"
    deli_csv = tmp_path / "ETN_SLO_2026_KPP_KPP_DELISTAVB_20260301.csv"
    output_csv = tmp_path / "train.csv"
    rn_csv = tmp_path / "x_RN_SLO_NASLOVI_register_naslovov_20260301.csv"
    ev_stavba_csv = tmp_path / "x_EV_SLO_EVIDENCA_VREDNOTENJA_stavba_20260314.csv"
    ev_del_csv = tmp_path / "x_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_20260314.csv"
    ev_del_enota_csv = tmp_path / "x_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_enota_20260314.csv"
    emv_zip = tmp_path / "x_emv_vredn_cone_17_VSE_2025.zip"

    pd.DataFrame(
        {
            "ID_POSLA": ["100"],
            "POGODBENA_CENA_ODSKODNINA": [240000],
            "TRZNOST_POSLA": [1],
            "VRSTA_KUPOPRODAJNEGA_POSLA": [1],
            "RPE_OBCINE_SIFRA": [61],
            "IME_OBCINE": ["Ljubljana"],
        }
    ).to_csv(posli_csv, index=False)

    pd.DataFrame(
        {
            "ID_POSLA": ["100"],
            "ID_DELA_STAVBE": ["77"],
            "SIFRA_KO": [1333],
            "IME_KO": ["Moste"],
            "OBCINA": ["Ljubljana"],
            "STEVILKA_STAVBE": [194],
            "STEVILKA_DELA_STAVBE": [1],
            "NASELJE": ["Ljubljana"],
            "ULICA": ["Polje cesta V"],
            "HISNA_STEVILKA": [4],
            "DODATEK_HS": [""],
            "PRODANA_POVRSINA": [80],
            "STEVILO_SOB": [3],
            "DEJANSKA_RABA_DELA_STAVBE": [2],
            "LETO_IZGRADNJE_DELA_STAVBE": [2001],
            "E_CENTROID": [np.nan],
            "N_CENTROID": [np.nan],
        }
    ).to_csv(deli_csv, index=False)

    pd.DataFrame(
        {
            "OBCINA_SIFRA": [61],
            "OBCINA_NAZIV": ["Ljubljana"],
            "NASELJE_NAZIV": ["Ljubljana"],
            "ULICA_NAZIV": ["Polje cesta V"],
            "HS_STEVILKA": [4],
            "HS_DODATEK": [""],
            "E": [467169],
            "N": [101799],
            "EID_NASLOV": [101400002022822009],
            "EID_NASELJE": [110300000101100844],
            "EID_ULICA": [110400000162051687],
            "EID_STAVBA": [100200000260407131],
            "EID_STATISTICNA_REGIJA": [111100000183622954],
        }
    ).to_csv(rn_csv, index=False)

    pd.DataFrame(
        {
            "EID_STAVBA": [100200000260407131],
            "KO_SIFKO": [1333],
            "STEV_ST": [194],
            "ST_ETAZ": [2],
            "LETO_IZG_STA": [1900],
            "LETO_OBN_STREHE": [1978],
            "LETO_OBN_FASADE": [2005],
            "ID_KONSTRUKCIJA": [4],
            "IMA_VODOVOD_DN": [1],
            "IMA_ELEKTRIKO_DN": [1],
            "IMA_KANALIZACIJO_DN": [1],
            "IMA_PLIN_DN": [0],
            "ID_TIP_STAVBE": [1],
            "ST_STANOVANJ": [4],
            "ST_POSLOVNIH_PROSTOROV": [0],
            "POV_STAVBE": [120],
            "RPE_OBCINE_SIFRA": [61],
        }
    ).to_csv(ev_stavba_csv, index=False)

    pd.DataFrame(
        {
            "EID_DEL_STAVBE": [100300000309048267],
            "EID_STAVBA": [100200000260407131],
            "STEV_DST": [1],
            "POVRSINA": [80],
            "UPOR_POV": [76],
            "LETO_OBN_OKEN": [2010],
            "LETO_OBN_INST": [2012],
            "ST_NADSTROPJA": [2],
            "ID_LEGA": [33],
            "IMA_DVIGALO_DN": [1],
            "VISINA_ETAZE": [2.7],
            "ID_DR_DST": [29],
            "ZPS_DST": [100],
        }
    ).to_csv(ev_del_csv, index=False)

    pd.DataFrame(
        {
            "EID_DEL_STAVBE": [100300000309048267],
            "ID_MODEL": ["GAR"],
            "RAVEN": ["10/20"],
            "VPLIV": [""],
            "POSPLOSENA_VREDNOST": [10800],
        }
    ).to_csv(ev_del_enota_csv, index=False)

    emv_zip.write_bytes(b"placeholder")

    monkeypatch.setattr(dps, "_get_optional_geopandas", lambda: object())
    monkeypatch.setattr(dps, "_resolve_emv_gpkg_path", lambda _path: str(tmp_path / "emv.gpkg"))

    def fake_match_emv_layer_to_rows(frame, row_index, *, gpkg_path, layer_name):
        if layer_name != "emv_vredn_cone_STA":
            return pd.DataFrame(index=row_index)
        return pd.DataFrame(
            {
                "IME": ["Ljubljana center"],
                "MODEL": ["STA"],
                "ID": ["STA-001"],
                "ST_RAVNI": [4],
                "DAT_VELJ": ["2025-01-01"],
            },
            index=row_index,
        )

    monkeypatch.setattr(dps, "_match_emv_layer_to_rows", fake_match_emv_layer_to_rows)

    result = prepare_training_csv_from_etn_kpp(str(posli_csv), str(deli_csv), str(output_csv))

    prepared = pd.read_csv(output_csv)
    metadata = load_training_metadata(str(output_csv))

    assert result["enrichment_summary"]["rn"]["rows_with_exact_address"] == 1
    assert result["enrichment_summary"]["ev"]["rows_with_building_match"] == 1
    assert prepared.loc[0, "rn_address_match"] == pytest.approx(1.0)
    assert prepared.loc[0, "ev_st_etaz"] == pytest.approx(2.0)
    assert prepared.loc[0, "ev_del_upor_pov"] == pytest.approx(76.0)
    assert prepared.loc[0, "ev_ima_dvigalo"] == pytest.approx(1.0)
    assert prepared.loc[0, "ev_benchmark_price_eur"] == pytest.approx(10800.0)
    assert prepared.loc[0, "ev_benchmark_price_per_m2"] == pytest.approx(135.0)
    assert prepared.loc[0, "emv_zone_match"] == pytest.approx(1.0)
    assert prepared.loc[0, "emv_zone_level"] == pytest.approx(4.0)
    assert prepared.loc[0, "emv_zone_model"] == "STA"
    assert prepared.loc[0, "emv_zone_name"] == "Ljubljana center"
    assert prepared.loc[0, "longitude"] == pytest.approx(467169.0)
    assert prepared.loc[0, "latitude"] == pytest.approx(101799.0)
    assert metadata is not None
    assert metadata["enrichment_summary"]["rn"]["available"] is True
    assert metadata["reports"][0]["enrichment_summary"]["ev"]["rows_with_building_match"] == 1
    assert metadata["reports"][0]["enrichment_summary"]["ev"]["rows_with_building_value_match"] == 1
    assert result["enrichment_summary"]["emv"]["available"] is True
    assert result["enrichment_summary"]["emv"]["rows_with_zone_match"] == 1
    assert metadata["reports"][0]["enrichment_summary"]["emv"]["matched_by_layer"]["emv_vredn_cone_STA"] == 1


def test_ev_benchmark_adjusted_by_sold_share(tmp_path, monkeypatch):
    """ev_benchmark_price_eur must be scaled by the sold-share fraction."""
    from app.services.data_processing_service import apply_gurs_deterministic_enrichment

    # Use small EIDs that survive float64 → int roundtrip (large EIDs lose precision)
    ev_del_enota_csv = tmp_path / "x_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_enota_20260314.csv"
    pd.DataFrame(
        {
            "EID_DEL_STAVBE": [9001, 9002],
            "ID_MODEL": ["STA", "STA"],
            "RAVEN": ["10/20", "10/20"],
            "VPLIV": ["", ""],
            "POSPLOSENA_VREDNOST": [200000, 100000],
        }
    ).to_csv(ev_del_enota_csv, index=False)

    ev_stavba_csv = tmp_path / "x_EV_SLO_EVIDENCA_VREDNOTENJA_stavba_20260314.csv"
    pd.DataFrame({"EID_STAVBA": [8001], "KO_SIFKO": [1333], "STEV_ST": [194], "ST_ETAZ": [2]}).to_csv(
        ev_stavba_csv, index=False
    )

    ev_del_csv = tmp_path / "x_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_20260314.csv"
    pd.DataFrame(
        {
            "EID_DEL_STAVBE": [9001, 9002],
            "EID_STAVBA": [8001, 8001],
            "STEV_DST": [1, 2],
            "POVRSINA": [80, 50],
            "UPOR_POV": [76, 48],
        }
    ).to_csv(ev_del_csv, index=False)

    training_df = pd.DataFrame(
        {
            "sifra_ko": [1333, 1333],
            "stevilka_stavbe": [194, 194],
            "stevilka_dela_stavbe": [1, 2],
            "size_m2": [80, 50],
            "price_eur": [100000, 100000],
            "prodani_delez_dela_stavbe": [0.5, 1.0],
            "prodani_delez_parcele": [np.nan, np.nan],
            "property_type": ["stanovanje", "stanovanje"],
            "municipality": ["Ljubljana", "Ljubljana"],
        }
    )

    result, _ = apply_gurs_deterministic_enrichment(
        training_df, upload_dir=str(tmp_path), enrichment_options={"enable_rn": False, "enable_emv": False}
    )

    # Row 0: 50% share → 200000 * 0.5 = 100000
    assert result.loc[0, "ev_benchmark_price_eur"] == pytest.approx(100000.0)
    # Row 1: 100% share → no adjustment → stays 100000
    assert result.loc[1, "ev_benchmark_price_eur"] == pytest.approx(100000.0)


def test_prepare_training_csv_from_etn_kpp_bulk_passes_enrichment_options(tmp_path, monkeypatch):
    captured: list[dict | None] = []
    frame = pd.DataFrame(
        [
            {
                "source_row_key": "deal-1:part-1",
                "size_m2": 50,
                "year_built": 2001,
                "municipality": "ljubljana",
                "property_type": "stanovanje",
                "price_eur": 200000,
            }
        ]
    )

    monkeypatch.setattr("app.services.data_processing_service.read_csv_flexible", lambda _path: pd.DataFrame())
    monkeypatch.setattr(
        "app.services.data_processing_service.build_training_df_from_etn_kpp",
        lambda *_args, **_kwargs: (frame.copy(), {"filter_stats": {"stages": []}}),
    )

    def fake_enrichment(prepared, *, upload_dir, enrichment_options=None, **_kwargs):
        captured.append(enrichment_options)
        return prepared, {"options": enrichment_options or {}}

    monkeypatch.setattr(
        "app.services.data_processing_service.apply_gurs_deterministic_enrichment",
        fake_enrichment,
    )

    options = {
        "enable_rn": True,
        "enable_ev": False,
        "enable_kn": True,
        "enable_gji": False,
        "enable_emv": False,
        "variant_label": "rn_only",
    }
    output_csv = tmp_path / "train.csv"

    result = prepare_training_csv_from_etn_kpp_bulk(
        [{"posli_csv_path": "2024_posli.csv", "delistavb_csv_path": "2024_deli.csv", "label": "2024"}],
        str(output_csv),
        enrichment_options=options,
    )

    assert captured == [{**options, "enable_dtm": True}]
    assert result["enrichment_options"] == {**options, "enable_dtm": True}


def test_resolve_enrichment_options_includes_kn_and_gji_in_variant_label():
    resolved = resolve_enrichment_options(
        {
            "enable_rn": True,
            "enable_ev": True,
            "enable_kn": False,
            "enable_gji": True,
            "enable_emv": False,
        }
    )

    assert resolved["variant_label"] == "rn+ev+gji"


def test_apply_gurs_deterministic_enrichment_applies_kn_and_gji_summaries(tmp_path, monkeypatch):
    training_df = pd.DataFrame(
        {
            "sifra_ko": [1333],
            "longitude": [467169],
            "latitude": [101799],
            "size_m2": [80],
            "price_eur": [240000],
            "property_type": ["stanovanje"],
            "municipality": ["Ljubljana"],
        }
    )

    monkeypatch.setattr(
        "app.services.data_processing_service.discover_gurs_enrichment_sources",
        lambda _upload_dir: {
            "kn_kat_obcine": str(tmp_path / "KN_SLO_KAT_OBCINE_20260315.zip"),
            "gji_vodovod": str(tmp_path / "KGI_SLO_GJI_VODOVOD_linije_20260314.gpkg"),
            "gji_kanalizacija": str(tmp_path / "KGI_SLO_GJI_KANALIZACIJA_linije_20260314.gpkg"),
        },
    )

    def fake_kn(prepared, *, discovered_sources):
        prepared = prepared.copy()
        prepared["kn_ko_polygon_match"] = 1
        prepared["kn_ko_name"] = "Moste"
        prepared["kn_in_ggo"] = 0
        return prepared, {
            "available": True,
            "ggo_available": False,
            "polygon_enabled": True,
            "gpkg_ready": True,
            "rows_with_coordinates": 1,
            "rows_with_sifra_ko_match": 1,
            "rows_with_polygon_match": 1,
            "rows_with_ggo_match": 0,
        }

    def fake_gji(prepared, *, discovered_sources):
        prepared = prepared.copy()
        prepared["gji_vodovod_distance_m"] = 35.0
        prepared["gji_vodovod_nearby_100m"] = 1.0
        prepared["gji_kanalizacija_distance_m"] = 110.0
        prepared["gji_kanalizacija_nearby_100m"] = 0.0
        return prepared, {
            "available": True,
            "spatial_enabled": True,
            "rows_with_coordinates": 1,
            "vodovod_available": True,
            "kanalizacija_available": True,
            "rows_with_vodovod_distance": 1,
            "rows_with_kanalizacija_distance": 1,
        }

    monkeypatch.setattr("app.services.data_processing_service._apply_kn_polygon_enrichment", fake_kn)
    monkeypatch.setattr("app.services.data_processing_service._apply_gji_infrastructure_enrichment", fake_gji)

    result, summary = dps.apply_gurs_deterministic_enrichment(
        training_df,
        upload_dir=str(tmp_path),
        enrichment_options={
            "enable_rn": False,
            "enable_ev": False,
            "enable_kn": True,
            "enable_gji": True,
            "enable_emv": False,
        },
    )

    assert result.loc[0, "kn_ko_polygon_match"] == pytest.approx(1.0)
    assert result.loc[0, "kn_ko_name"] == "Moste"
    assert result.loc[0, "gji_vodovod_distance_m"] == pytest.approx(35.0)
    assert summary["kn"]["rows_with_polygon_match"] == 1
    assert summary["gji"]["rows_with_vodovod_distance"] == 1


def test_apply_gji_infrastructure_enrichment_tracks_nearby_counts(tmp_path, monkeypatch):
    training_df = pd.DataFrame(
        {
            "longitude": [467169.0, 467500.0],
            "latitude": [101799.0, 102100.0],
        }
    )

    monkeypatch.setattr(dps, "_get_optional_geopandas", lambda: object())
    monkeypatch.setattr(dps, "_resolve_vector_gpkg_path", lambda source_path, preferred_name="": source_path)

    distances = {
        str(tmp_path / "vodovod.gpkg"): pd.Series([35.0, 130.0], index=training_df.index, dtype="float64"),
        str(tmp_path / "kanalizacija.gpkg"): pd.Series([210.0, 80.0], index=training_df.index, dtype="float64"),
    }

    def fake_nearest(frame, row_index, *, gpkg_path, layer_name=None):
        return distances[gpkg_path].reindex(row_index)

    monkeypatch.setattr(dps, "_nearest_distances_to_layer", fake_nearest)

    result, summary = dps._apply_gji_infrastructure_enrichment(
        training_df,
        discovered_sources={
            "gji_vodovod": str(tmp_path / "vodovod.gpkg"),
            "gji_kanalizacija": str(tmp_path / "kanalizacija.gpkg"),
        },
    )

    assert result["gji_vodovod_nearby_100m"].tolist() == pytest.approx([1.0, 0.0])
    assert result["gji_kanalizacija_nearby_100m"].tolist() == pytest.approx([0.0, 1.0])
    assert summary["rows_with_vodovod_distance"] == 2
    assert summary["rows_with_kanalizacija_distance"] == 2
    assert summary["rows_with_vodovod_nearby_100m"] == 1
    assert summary["rows_with_kanalizacija_nearby_100m"] == 1


def test_apply_gurs_deterministic_enrichment_falls_back_to_municipality_name_for_rn(tmp_path):
    rn_csv = tmp_path / "x_RN_SLO_NASLOVI_register_naslovov_20260301.csv"
    pd.DataFrame(
        {
            "OBCINA_SIFRA": [23],
            "OBCINA_NAZIV": ["Domzale"],
            "NASELJE_NAZIV": ["DOMZALE"],
            "ULICA_NAZIV": ["VODNIKOVA ULICA"],
            "HS_STEVILKA": [3],
            "HS_DODATEK": ["A"],
            "E": [467169],
            "N": [101799],
            "EID_NASLOV": [12345],
            "EID_NASELJE": [23456],
            "EID_ULICA": [34567],
            "EID_STAVBA": [45678],
            "EID_STATISTICNA_REGIJA": [56789],
        }
    ).to_csv(rn_csv, index=False)

    training_df = pd.DataFrame(
        {
            "municipality": ["Domzale"],
            "rpe_obcine_sifra": [np.nan],
            "naselje": ["DOMZALE"],
            "ulica": ["VODNIKOVA ULICA"],
            "hisna_stevilka": ["3.0"],
            "dodatek_hs": ["a"],
            "property_type": ["stanovanje"],
            "price_eur": [200000],
            "size_m2": [80],
        }
    )

    result, summary = dps.apply_gurs_deterministic_enrichment(
        training_df,
        upload_dir=str(tmp_path),
        enrichment_options={
            "enable_rn": True,
            "enable_ev": False,
            "enable_kn": False,
            "enable_gji": False,
            "enable_emv": False,
        },
    )

    assert result.loc[0, "rn_address_match"] == pytest.approx(1.0)
    assert result.loc[0, "eid_statisticna_regija"] == pytest.approx(56789)
    assert summary["rn"]["rows_with_exact_address"] == 1
