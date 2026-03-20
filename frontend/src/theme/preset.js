import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

const MarketPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eff4ff',
      100: '#dfe9ff',
      200: '#c6d7fe',
      300: '#a3bbfc',
      400: '#7897f8',
      500: '#4b6fed',
      600: '#1d4ed8',
      700: '#1e40af',
      800: '#1e3a8a',
      900: '#1d326d',
      950: '#162347',
    },
    colorScheme: {
      light: {
        surface: {
          0: '#ffffff',
          50: '#f8fbfd',
          100: '#eef4f7',
          200: '#dbe5ee',
          300: '#bfd0df',
          400: '#8ea1b5',
          500: '#627487',
          600: '#4a5b6d',
          700: '#334255',
          800: '#1e293b',
          900: '#0f172a',
        },
      },
      dark: {
        surface: {
          0: '#020817',
          50: '#07111d',
          100: '#0d1b2d',
          200: '#16263b',
          300: '#22364d',
          400: '#395470',
          500: '#5b7898',
          600: '#84a2c4',
          700: '#b2cae5',
          800: '#dce8f6',
          900: '#f3f8ff',
        },
      },
    },
  },
})

export default MarketPreset
