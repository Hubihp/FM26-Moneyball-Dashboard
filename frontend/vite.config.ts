import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Zbudowany frontend trafia do pakietu Pythona i jest serwowany przez FastAPI,
// wiec uzytkownik nie potrzebuje Node.js. W trybie deweloperskim /api idzie do serwera :8765.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../fm_moneyball/serwer/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 4000,
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8765' },
  },
});
