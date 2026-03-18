<script setup lang="ts">
  import type { LayerGroup, Map as LeafletMap } from 'leaflet'

  interface Transaction {
    lat: number
    lng: number
    price_per_m2: number
    municipality: string
    property_type: string
    price_eur: number
    size_m2: number
    year: number
  }

  const props = defineProps<{
    transactions: Transaction[]
    selectedBand?: 'low' | 'mid' | 'high' | null
  }>()

  const emit = defineEmits<{
    select: [transaction: Transaction]
  }>()

  const mapContainer = ref<HTMLElement | null>(null)
  let map: LeafletMap | null = null
  let markersLayer: LayerGroup | null = null

  function getBandColor(pricePerM2: number, thresholds: { low: number; high: number }): string {
    if (pricePerM2 < thresholds.low) return '#22c55e' // green = low
    if (pricePerM2 < thresholds.high) return '#f59e0b' // yellow = mid
    return '#ef4444' // red = high
  }

  onMounted(async () => {
    const L = await import('leaflet')
    await import('leaflet/dist/leaflet.css')
    if (!mapContainer.value) return

    map = L.map(mapContainer.value, { preferCanvas: true }).setView([46.1512, 14.9955], 8)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map)

    markersLayer = L.layerGroup().addTo(map)
    updateMarkers(L)
  })

  watch(
    () => props.transactions,
    async () => {
      const L = await import('leaflet')
      updateMarkers(L)
    },
  )

  function updateMarkers(L: typeof import('leaflet')) {
    if (!map || !markersLayer) return
    markersLayer.clearLayers()
    if (!props.transactions.length) return

    const prices = props.transactions.map((t) => t.price_per_m2).sort((a, b) => a - b)
    const thresholds = {
      low: prices[Math.floor(prices.length * 0.33)] ?? 0,
      high: prices[Math.floor(prices.length * 0.66)] ?? 0,
    }

    for (const t of props.transactions) {
      const color = getBandColor(t.price_per_m2, thresholds)
      const marker = L.circleMarker([t.lat, t.lng], {
        radius: 6,
        fillColor: color,
        color: '#fff',
        weight: 1.5,
        fillOpacity: 0.85,
      }).addTo(markersLayer)

      marker.on('click', () => emit('select', t))
    }
  }

  onUnmounted(() => {
    if (map) {
      map.remove()
      map = null
    }
  })
</script>

<template>
  <div ref="mapContainer" class="map-container" />
</template>

<style scoped>
  .map-container {
    width: 100%;
    height: 100%;
    min-height: 500px;
    border-radius: 1.5rem;
    overflow: hidden;
  }
</style>
