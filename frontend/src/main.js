import { createApp } from 'vue'
import ConfirmationService from 'primevue/confirmationservice'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Tooltip from 'primevue/tooltip'
import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import { pinia } from './stores'
import MarketPreset from './theme/preset'
import 'primeicons/primeicons.css'
import './styles/main.css'

const app = createApp(App)
app.use(pinia)
app.use(PrimeVue, {
  ripple: false,
  inputVariant: 'filled',
  theme: {
    preset: MarketPreset,
    options: {
      darkModeSelector: '[data-theme="dark"]',
    },
  },
})
app.use(ToastService)
app.use(ConfirmationService)
app.use(router)
app.use(i18n)
app.directive('tooltip', Tooltip)
app.mount('#app')
