import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ArcoVue from '@arco-design/web-vue'
import '@arco-design/web-vue/dist/arco.css'
import DemoApp from './demo/DemoApp.vue'
import './style.css'

createApp(DemoApp).use(createPinia()).use(ArcoVue).mount('#app')
