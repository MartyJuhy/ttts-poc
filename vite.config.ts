import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
	plugins: [react()],
	server: {
		proxy: {
			'/api/history': {
				target: 'http://localhost:8000',
				changeOrigin: true,
			},
			'/api': {
				target: 'http://localhost:5080',
				changeOrigin: true,
			},
		},
	},
})