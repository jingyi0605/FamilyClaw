import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'

import DocImage from './components/DocImage.vue'
import './custom.css'

const theme: Theme = {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('DocImage', DocImage)
  }
}

export default theme
