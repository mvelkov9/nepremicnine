import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

const MarketPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#edf3ff',
      100: '#dbe7ff',
      200: '#bfd3ff',
      300: '#97b8ff',
      400: '#6792ff',
      500: '#3f78f4',
      600: '#2265e5',
      700: '#174db9',
      800: '#143f95',
      900: '#163674',
      950: '#102149',
    },
    colorScheme: {
      light: {
        surface: {
          0: '#ffffff',
          50: '#f8fbff',
          100: '#edf3fb',
          200: '#dce6f1',
          300: '#c0cedd',
          400: '#8fa1b7',
          500: '#667a92',
          600: '#4c6076',
          700: '#36475d',
          800: '#213248',
          900: '#111d2d',
        },
      },
      dark: {
        surface: {
          0: '#040912',
          50: '#08111c',
          100: '#0f1828',
          200: '#162235',
          300: '#1d2d44',
          400: '#465971',
          500: '#70849a',
          600: '#99aec1',
          700: '#c5d5e3',
          800: '#e3edf8',
          900: '#f7fbff',
        },
      },
    },
  },
})

export default MarketPreset
