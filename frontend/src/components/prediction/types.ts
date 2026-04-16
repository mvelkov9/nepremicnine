export interface PredictionFormData {
  size_m2: number | null
  rooms: number | null
  year_built: number | null
  floor: number | null
  latitude: number | null
  longitude: number | null
  naselje: string
  municipality: string
  ime_ko: string
  property_type: string
  uporabna_povrsina: number | null
  lega_v_stavbi: string
  novogradnja: number
  has_garaza: number
  has_klet: number
  has_shramba: number
  has_terasa: number
  stavba_je_dokoncana: number
  ddv_vkljucen: number
}

export interface PredictionResultPayload {
  predicted_price_eur: number
  model_used: string
  routing_mode?: string | null
  type_blend_weight?: number | null
  calibration_factor?: number | null
  calibration_source?: string | null
  features_used: Record<string, string>
}

export interface PredictionHistoryItem {
  id: number
  payload: {
    municipality?: string | null
    property_type?: string | null
    size_m2?: number | null
    uporabna_povrsina?: number | null
    naselje?: string | null
    year_built?: number | null
    floor?: number | null
  } & Record<string, unknown>
  predicted_price_eur: number | null
  created_at: string
}

export interface PredictionSummaryCard {
  key: string
  icon: string
  label: string
  value: string
  detail?: string
}

export interface PredictionReadinessItem {
  key: string
  ready: boolean
  text: string
}

export type PredictionRouteQuery = Partial<
  Record<
    'naselje' | 'municipality' | 'property_type' | 'size_m2' | 'year_built' | 'floor' | 'price_eur',
    string | string[] | null | undefined
  >
>
