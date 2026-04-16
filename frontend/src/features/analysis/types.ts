export interface GuidedAnalysisForm {
  naselje: string
  municipality: string
  ime_ko: string
  property_type: string
  size_m2: number
  uporabna_povrsina: number | null
  rooms: number | null
  year_built: number | null
  floor: number | null
  lega_v_stavbi: string
  novogradnja: number
  has_garaza: number
  has_klet: number
  has_shramba: number
  has_terasa: number
  stavba_je_dokoncana: number
  ddv_vkljucen: number
  asking_price: number | null
  notes: string
}

export type AnalysisBinaryField =
  | 'novogradnja'
  | 'has_garaza'
  | 'has_klet'
  | 'has_shramba'
  | 'has_terasa'
  | 'stavba_je_dokoncana'
  | 'ddv_vkljucen'

export interface AnalysisListing {
  municipality?: string | null
  naselje?: string | null
  property_type?: string | null
  size_m2?: number | null
  uporabna_povrsina?: number | null
  rooms?: number | null
  year_built?: number | null
  floor?: number | null
  asking_price?: number | null
  predicted_price?: number | null
  deviation_pct?: number | null
  deviation_percent?: number | null
  label?: string | null
}

export interface AnalysisResultPayload {
  listings?: AnalysisListing[]
}

export interface AnalysisSummaryCard {
  key: string
  label: string
  value: string
  hint: string
}

export interface AnalysisHeroMetric {
  key: string
  title: string
  value: string
  body: string
}

export interface AnalysisHeroPill {
  key: string
  label: string
  value: string
}

export interface AnalysisReadinessItem {
  key: string
  ready: boolean
  text: string
}
