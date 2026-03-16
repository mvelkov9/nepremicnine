import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

const MarketPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#f3f8f7',
      100: '#dcefeb',
      200: '#badfd8',
      300: '#8dc8be',
      400: '#58aa9d',
      500: '#2d8479',
      600: '#236a63',
      700: '#1e554f',
      800: '#1a4440',
      900: '#173935',
      950: '#0d221f',
    },
    colorScheme: {
      light: {
        surface: {
          0: '#ffffff',
          50: '#f8faf8',
          100: '#f1f5f2',
          200: '#dce5df',
          300: '#c3d2c8',
          400: '#91a79b',
          500: '#657a70',
          600: '#4a5d54',
          700: '#34433d',
          800: '#202a26',
          900: '#111816',
        },
      },
      dark: {
        surface: {
          0: '#0b1110',
          50: '#101917',
          100: '#162321',
          200: '#223230',
          300: '#314744',
          400: '#4b6a64',
          500: '#6f9188',
          600: '#93b3aa',
          700: '#b9d1cb',
          800: '#d7e8e3',
          900: '#eef7f4',
        },
      },
    },
  },
})

export default MarketPreset
