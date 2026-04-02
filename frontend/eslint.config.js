import pluginVue from "eslint-plugin-vue";
import tsParser from "@typescript-eslint/parser";
import vueParser from "vue-eslint-parser";

export default [
  {
    ignores: [
      "dist/",
      "coverage/",
      ".pnpm-store/",
      ".vite/",
      "node_modules/",
      "playwright-report/",
      "test-results/",
    ],
  },
  {
    files: ["**/*.{js,mjs,cjs,ts,mts,cts}"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: "latest",
      sourceType: "module",
    },
  },
  ...pluginVue.configs["flat/recommended"],
  {
    files: ["**/*.vue"],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: "latest",
        sourceType: "module",
        extraFileExtensions: [".vue"],
      },
    },
  },
  {
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/no-unused-vars": "warn",
      "vue/require-default-prop": "off",
      "vue/max-attributes-per-line": "off",
      "vue/html-indent": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/html-self-closing": "off",
      "vue/html-closing-bracket-newline": "off",
      "vue/first-attribute-linebreak": "off",
      "vue/attributes-order": "off",
    },
  },
];
