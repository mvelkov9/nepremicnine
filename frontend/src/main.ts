import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import Tooltip from 'primevue/tooltip'
import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import MarketPreset from './theme/preset'
import 'primeicons/primeicons.css'
import './styles/main.css'
import './utils/chartSetup'

const app = createApp(App)
app.use(createPinia())
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
app.use(ConfirmationService)
app.use(ToastService)
app.use(router)
app.use(i18n)
app.directive('tooltip', Tooltip)
app.mount('#app')
