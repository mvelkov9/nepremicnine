export interface GursEnrichmentRow {
  label: string
  sources: string[]
  matchedSources: string[]
  rnAvailable: boolean
  evBuildingAvailable: boolean
  evParcelAvailable: boolean
  knAvailable: boolean
  gjiAvailable: boolean
  emvAvailable: boolean
  emvSpatialEnabled: boolean
  rnExactAddress: number
  rnRegionId: number
  evBuildingMatch: number
  evParcelMatch: number
  knPolygonMatch: number
  gjiVodovodNearby: number
  gjiKanalizacijaNearby: number
  emvZoneMatch: number
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function toInt(value: unknown): number {
  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? numericValue : 0
}

function buildRow(label: string, summaries: unknown[]): GursEnrichmentRow {
  const sources = new Set<string>()
  const matchedSources = new Set<string>()
  let rnAvailable = false
  let evBuildingAvailable = false
  let evParcelAvailable = false
  let knAvailable = false
  let gjiAvailable = false
  let emvAvailable = false
  let emvSpatialEnabled = false
  let rnExactAddress = 0
  let rnRegionId = 0
  let evBuildingMatch = 0
  let evParcelMatch = 0
  let knPolygonMatch = 0
  let gjiVodovodNearby = 0
  let gjiKanalizacijaNearby = 0
  let emvZoneMatch = 0

  for (const summaryValue of summaries) {
    const summary = asRecord(summaryValue)
    const sourceMap = asRecord(summary.sources)
    for (const sourceName of Object.values(sourceMap)) {
      if (sourceName) {
        sources.add(String(sourceName))
      }
    }

    const rn = asRecord(summary.rn)
    const ev = asRecord(summary.ev)
    const kn = asRecord(summary.kn)
    const gji = asRecord(summary.gji)
    const emv = asRecord(summary.emv)

    rnAvailable = rnAvailable || Boolean(rn.available)
    evBuildingAvailable = evBuildingAvailable || Boolean(ev.building_available)
    evParcelAvailable = evParcelAvailable || Boolean(ev.parcel_available)
    knAvailable = knAvailable || Boolean(kn.available)
    gjiAvailable = gjiAvailable || Boolean(gji.available)
    emvAvailable = emvAvailable || Boolean(emv.available)
    emvSpatialEnabled = emvSpatialEnabled || Boolean(emv.spatial_enabled)
    rnExactAddress += toInt(rn.rows_with_exact_address)
    rnRegionId += toInt(rn.rows_with_region_id)
    evBuildingMatch += toInt(ev.rows_with_building_match)
    evParcelMatch += toInt(ev.rows_with_parcel_match)
    knPolygonMatch += toInt(kn.rows_with_sifra_ko_match) + toInt(kn.rows_with_polygon_match)
    gjiVodovodNearby += toInt(gji.rows_with_vodovod_nearby_100m)
    gjiKanalizacijaNearby += toInt(gji.rows_with_kanalizacija_nearby_100m)
    emvZoneMatch += toInt(emv.rows_with_zone_match)

    const rnMatched = toInt(rn.rows_with_exact_address) > 0 || toInt(rn.rows_with_region_id) > 0
    if (rnMatched && sourceMap.rn) {
      matchedSources.add(String(sourceMap.rn))
    }

    if (toInt(ev.rows_with_building_match) > 0) {
      for (const key of ['ev_stavba', 'ev_del_stavbe', 'ev_del_stavbe_enota']) {
        if (sourceMap[key]) {
          matchedSources.add(String(sourceMap[key]))
        }
      }
    }

    if (toInt(ev.rows_with_parcel_match) > 0) {
      for (const key of ['ev_parcela', 'ev_parc_enota']) {
        if (sourceMap[key]) {
          matchedSources.add(String(sourceMap[key]))
        }
      }
    }

    if (toInt(emv.rows_with_zone_match) > 0 && sourceMap.emv) {
      matchedSources.add(String(sourceMap.emv))
    }

    if (toInt(kn.rows_with_polygon_match) > 0 || toInt(kn.rows_with_sifra_ko_match) > 0) {
      for (const key of ['kn_kat_obcine', 'kn_ggo']) {
        if (sourceMap[key]) {
          matchedSources.add(String(sourceMap[key]))
        }
      }
    }

    if (
      toInt(gji.rows_with_vodovod_nearby_100m) > 0 ||
      toInt(gji.rows_with_kanalizacija_nearby_100m) > 0
    ) {
      for (const key of ['gji_vodovod', 'gji_kanalizacija']) {
        if (sourceMap[key]) {
          matchedSources.add(String(sourceMap[key]))
        }
      }
    }
  }

  return {
    label,
    sources: Array.from(sources).sort(),
    matchedSources: Array.from(matchedSources).sort(),
    rnAvailable,
    evBuildingAvailable,
    evParcelAvailable,
    knAvailable,
    gjiAvailable,
    emvAvailable,
    emvSpatialEnabled,
    rnExactAddress,
    rnRegionId,
    evBuildingMatch,
    evParcelMatch,
    knPolygonMatch,
    gjiVodovodNearby,
    gjiKanalizacijaNearby,
    emvZoneMatch,
  }
}

export function buildGursEnrichmentRows(
  reports: unknown[] | null | undefined,
  enrichmentSummary: unknown,
): GursEnrichmentRow[] {
  const safeReports = Array.isArray(reports) ? reports : []
  const summaryRecord = asRecord(enrichmentSummary)
  const mergedSummary = asRecord(summaryRecord.merged)
  if (Object.keys(mergedSummary).length) {
    return [buildRow('single', [mergedSummary])]
  }

  const okReports = safeReports.filter(
    (report) => asRecord(report).status === 'ok' && asRecord(report).enrichment_summary,
  )

  if (okReports.length) {
    return okReports.map((report) => {
      const reportRecord = asRecord(report)
      return buildRow(String(reportRecord.label || 'run'), [
        reportRecord.enrichment_summary,
        reportRecord.land_enrichment_summary,
      ])
    })
  }

  const yearsRecord = asRecord(summaryRecord.years)
  if (Object.keys(yearsRecord).length) {
    return Object.entries(yearsRecord).map(([label, summary]) => buildRow(label, [summary]))
  }

  if (Object.keys(summaryRecord).length) {
    return [buildRow('single', [summaryRecord])]
  }

  return []
}

export function summarizeGursEnrichment(rows: GursEnrichmentRow[]) {
  return rows.reduce(
    (accumulator, row) => ({
      runs: accumulator.runs + 1,
      rnExactAddress: accumulator.rnExactAddress + row.rnExactAddress,
      rnRegionId: accumulator.rnRegionId + row.rnRegionId,
      evBuildingMatch: accumulator.evBuildingMatch + row.evBuildingMatch,
      evParcelMatch: accumulator.evParcelMatch + row.evParcelMatch,
      knPolygonMatch: accumulator.knPolygonMatch + row.knPolygonMatch,
      gjiVodovodNearby: accumulator.gjiVodovodNearby + row.gjiVodovodNearby,
      gjiKanalizacijaNearby: accumulator.gjiKanalizacijaNearby + row.gjiKanalizacijaNearby,
      emvZoneMatch: accumulator.emvZoneMatch + row.emvZoneMatch,
    }),
    {
      runs: 0,
      rnExactAddress: 0,
      rnRegionId: 0,
      evBuildingMatch: 0,
      evParcelMatch: 0,
      knPolygonMatch: 0,
      gjiVodovodNearby: 0,
      gjiKanalizacijaNearby: 0,
      emvZoneMatch: 0,
    },
  )
}
