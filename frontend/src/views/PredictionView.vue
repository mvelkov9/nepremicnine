<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '../composables/useApi'

const { t } = useI18n()

const form = ref({
  size_m2: null,
  rooms: null,
  year_built: null,
  floor: null,
  latitude: null,
  longitude: null,
  municipality: '',
  property_type: 'stanovanje',
})

const propertyTypes = [
  'stanovanje', 'hisa', 'poslovni_prostor', 'industrijski',
  'turisticni', 'gostinstvo', 'garaza', 'kmetijsko',
]

const result = ref(null)
const history = ref([])
const loading = ref(false)
const error = ref(null)

async function predict() {
  loading.value = true
  error.value = null
  result.value = null
  try {
    const payload = {}
    for (const [key, val] of Object.entries(form.value)) {
      if (val !== null && val !== '' && val !== undefined) {
        payload[key] = val
      }
    }
    const { data } = await api.post('/api/predict', payload)
    result.value = data
    await fetchHistory()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  try {
    const { data } = await api.get('/api/predict/history?limit=20')
    history.value = data
  } catch {
    history.value = []
  }
}

onMounted(fetchHistory)
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.prediction') }}</h1>

    <div class="card" style="margin-bottom: 1.5rem">
      <h2>{{ t('predict.title') }}</h2>
      <form @submit.prevent="predict" class="predict-form">
        <div class="form-grid">
          <div>
            <label class="form-label">{{ t('predict.size') }} *</label>
            <input v-model.number="form.size_m2" type="number" step="0.1" min="1"
                   class="form-input" required />
          </div>
          <div>
            <label class="form-label">{{ t('predict.rooms') }}</label>
            <input v-model.number="form.rooms" type="number" step="0.5" min="0"
                   class="form-input" />
          </div>
          <div>
            <label class="form-label">{{ t('predict.yearBuilt') }}</label>
            <input v-model.number="form.year_built" type="number" min="1800" max="2030"
                   class="form-input" />
          </div>
          <div>
            <label class="form-label">{{ t('predict.floor') }}</label>
            <input v-model.number="form.floor" type="number" min="-2" max="50"
                   class="form-input" />
          </div>
          <div>
            <label class="form-label">{{ t('predict.latitude') }}</label>
            <input v-model.number="form.latitude" type="number" step="0.0001"
                   class="form-input" placeholder="46.05" />
          </div>
          <div>
            <label class="form-label">{{ t('predict.longitude') }}</label>
            <input v-model.number="form.longitude" type="number" step="0.0001"
                   class="form-input" placeholder="14.50" />
          </div>
          <div>
            <label class="form-label">{{ t('predict.municipality') }}</label>
            <input v-model="form.municipality" type="text" class="form-input"
                   placeholder="Ljubljana" />
          </div>
          <div>
            <label class="form-label">{{ t('predict.propertyType') }}</label>
            <select v-model="form.property_type" class="form-input">
              <option v-for="pt in propertyTypes" :key="pt" :value="pt">{{ pt }}</option>
            </select>
          </div>
        </div>

        <button type="submit" class="btn btn-primary" :disabled="loading || !form.size_m2"
                style="margin-top: 1rem">
          {{ loading ? t('common.loading') : t('predict.predictButton') }}
        </button>
      </form>

      <p v-if="error" class="error-text" style="margin-top: 1rem">{{ error }}</p>
    </div>

    <!-- Result -->
    <div v-if="result" class="card result-card" style="margin-bottom: 1.5rem">
      <h2>{{ t('predict.result') }}</h2>
      <div class="predicted-price">
        €{{ Math.round(result.predicted_price_eur).toLocaleString() }}
      </div>
      <p class="muted">{{ t('predict.modelUsed') }}: {{ result.model_used }}</p>
    </div>

    <!-- History -->
    <div v-if="history.length" class="card">
      <h2>{{ t('predict.history') }}</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('predict.date') }}</th>
              <th>{{ t('predict.size') }}</th>
              <th>{{ t('predict.propertyType') }}</th>
              <th>{{ t('predict.predictedPrice') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in history" :key="item.id">
              <td>{{ new Date(item.created_at).toLocaleString() }}</td>
              <td>{{ item.payload.size_m2 }} m²</td>
              <td>{{ item.payload.property_type || '-' }}</td>
              <td class="price">€{{ Math.round(item.predicted_price_eur).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.predict-form .form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
.result-card {
  text-align: center;
}
.predicted-price {
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--color-primary);
  margin: 1rem 0;
}
.price {
  font-weight: 600;
  color: var(--color-primary);
}
</style>
