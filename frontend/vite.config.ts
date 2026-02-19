import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

const backendPort = process.env['BACKEND_PORT'] || '8000';
const backendTarget = `http://localhost:${backendPort}`;

export default defineConfig({
	plugins: [tailwindcss(), sveltekit(), svelteTesting()],
	server: {
		proxy: {
			'/api': {
				target: backendTarget,
				changeOrigin: true
			},
			'/docs': {
				target: backendTarget,
				changeOrigin: true
			},
			'/redoc': {
				target: backendTarget,
				changeOrigin: true
			},
			'/openapi.json': {
				target: backendTarget,
				changeOrigin: true
			}
		}
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'jsdom'
	}
});
