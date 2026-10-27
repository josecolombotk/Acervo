import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// El proxy envía /api al backend Flask (puerto 5000) y mantiene la sesión en el mismo origen.
export default defineConfig({ plugins: [react()], server: { port: 5173, proxy: { '/api': 'http://localhost:5000' } } });
