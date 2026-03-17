import pluginVue from 'eslint-plugin-vue'

export default [
  ...pluginVue.configs['flat/recommended'],
  {
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/no-unused-vars': 'warn',
      'vue/require-default-prop': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-indent': 'off',
      'vue/html-self-closing': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/attributes-order': 'off',
    },
  },
  {
    ignores: [
      '.nuxt/',
      '.nuxt-app/',
      '.nuxt-build/',
      '.nuxt-dev/',
      '.nuxt-local/',
      '.nuxt-preview/',
      '.nuxt-typecheck/',
      '.nuxt-verify/',
      '.output/',
      '.output-build/',
      '.output-dev/',
      '.output-local/',
      '.output-typecheck/',
      '.output-verify/',
      '.vite-cache/',
      '.pnpm-store/',
      'dist/',
      'node_modules/',
    ],
  },
]
