/* eslint-env node */

module.exports = function (/* ctx */) {
  return {
    boot: ['axios', 'activity'],

    css: ['app.scss'],

    extras: [
      'roboto-font',
      'material-icons',
    ],

    build: {
      target: {
        browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'],
        node: 'node20',
      },
      vueRouterMode: 'hash',
    },

    devServer: {
      open: false,
      port: 9000,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: process.env.API_URL || 'http://localhost:8000',
          changeOrigin: true,
        },
        '/media': {
          target: process.env.API_URL || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },

    framework: {
      config: {
        brand: {
          primary: '#2E7D32',
          secondary: '#43A047',
          accent: '#81C784',
          dark: '#1C2526',
          'dark-page': '#141E1F',
          positive: '#21BA45',
          negative: '#C10015',
          info: '#31CCEC',
          warning: '#F2C037',
        },
        notify: {
          position: 'top-right',
          timeout: 3000,
        },
      },
      plugins: ['Notify', 'Dialog', 'Loading', 'LocalStorage'],
    },

    animations: [],
  }
}
