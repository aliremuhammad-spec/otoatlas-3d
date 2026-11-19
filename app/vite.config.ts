/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { en } from './src/i18n/en.ts';

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as { version: string };

// Relative base so the same build runs as a PWA, inside Capacitor and inside Tauri.
export default defineConfig({
  base: './',
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  plugins: [
    react(),
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'OtoAtlas 3D',
        short_name: 'OtoAtlas',
        // The credit comes from the catalog so the wording is identical everywhere.
        description: `${en['app.tagline']}. ${en['disclaimer.title']}. ${en['credit.supervision']}.`,
        display: 'standalone',
        orientation: 'any',
        background_color: '#0e1418',
        theme_color: '#0e1418',
        icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,woff2}'],
        // Specimen packages are installed beside the app after the build; keep the
        // ones the user has opened so they work without a network.
        runtimeCaching: [
          {
            urlPattern: /\/content\//,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'specimen-content' },
          },
          // Scans published on Hugging Face: each URL is pinned to a commit, so a cached copy never goes stale.
          {
            urlPattern: /^https:\/\/huggingface\.co\/datasets\/.+\/resolve\/[0-9a-f]{40}\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'specimen-scans',
              cacheableResponse: { statuses: [0, 200] },
              expiration: { maxEntries: 40 },
            },
          },
        ],
      },
    }),
  ],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
