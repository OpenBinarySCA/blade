import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import router from './router'
import App from './App.vue'

// Ant Design Vue — import its reset FIRST so our tokens/fonts win the cascade
import antdPlugin from './plugins/antd'
import 'ant-design-vue/dist/reset.css'

import './style.css'
import './styles/theme.css'

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)
app.use(pinia)
app.use(router)
app.use(antdPlugin)  // Add Ant Design Vue
app.mount('#app')
