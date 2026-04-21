# Production Audit Baseline (2026-04-05)

Historical snapshot of the pre-v15 production baseline. The code-backed v15 changes are
summarized in `v15_production_notes.md`; the metrics below remain useful as a baseline
comparison point.

Trained at: 2026-04-05T07:54:36.861844
CSV: /app/data/models/research_queue/prepared/train_2020_2026.csv
Window: {'year_source': 'transaction_year', 'start_year': 2020, 'end_year': 2026}

## garaza
features: 79 (69/10)
setup: rich / log_ppm2 / full_history_weighted
routing: blend / 0.7
metrics: R2 0.5401, MAPE 47.34
top: knn_dw10_log_ppm2, knn_type_10_log_ppm2, kn_ggo_section, knn_3_log_ppm2, knn_5_log_ppm2

## gostinstvo
features: 39 (35/4)
setup: rich / log_ppm2 / full_history_weighted
routing: blend / 0.2
metrics: R2 0.6131, MAPE 45.26
top: kn_ggo_section, emv_zone_id, emv_zone_name, ime_ko, knn_dw10_log_ppm2

## hisa
features: 77 (67/10)
setup: simple / log_ppm2 / recent_6y_weighted
routing: per_type_only / 1.0
metrics: R2 0.7683, MAPE 49.77
top: kn_ggo_section, naselje, ime_ko, comp_type_naselje_ppm2, emv_zone_id

## industrijski
features: 55 (47/8)
setup: rich / log_ppm2 / recent_3y_weighted
routing: blend / 0.8
metrics: R2 0.5842, MAPE 59.60
top: kn_ggo_section, emv_zone_id, emv_zone_name, ime_ko, knn_dw10_log_ppm2

## kmetijsko
features: 55 (45/10)
setup: simple / log_price / full_history_weighted
routing: blend / 0.7
metrics: R2 0.4833, MAPE 80.63
top: kn_ggo_section, ime_ko, comp_type_naselje_ppm2, emv_zone_id, emv_zone_name

## parcela
features: 61 (51/10)
setup: rich / log_price / recent_6y_weighted
routing: blend / 0.4
metrics: R2 0.6666, MAPE 56.74
top: kn_ggo_section, vrsta_zemljisca, parcela_namenska_raba, knn_type_10_log_ppm2, emv_zone_id

## poslovni_prostor
features: 60 (50/10)
setup: simple / log_price / full_history_weighted
routing: blend / 0.5
metrics: R2 0.7878, MAPE 32.36
top: kn_ggo_section, emv_zone_id, emv_zone_name, knn_dw10_log_ppm2, ime_ko

## stanovanje
features: 86 (75/11)
setup: rich / log_ppm2 / recent_6y_weighted
routing: blend / 0.9
metrics: R2 0.8057, MAPE 23.55
top: knn_dw10_log_ppm2, knn_type_10_log_ppm2, kn_ggo_section, knn_3_log_ppm2, knn_5_log_ppm2

## turisticni
features: 45 (39/6)
setup: simple / log_ppm2 / full_history_weighted
routing: blend / 0.25
metrics: R2 0.6082, MAPE 46.49
top: kn_ggo_section, emv_zone_id, emv_zone_name, ime_ko, knn_dw10_log_ppm2
