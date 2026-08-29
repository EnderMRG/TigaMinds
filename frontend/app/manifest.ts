import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'CHAI-NET - AI Tea Cultivation Intelligence',
    short_name: 'CHAI-NET',
    description: 'Intelligent IoT cultivation monitoring, AI leaf quality grading, market price forecasting, and harvest optimization for tea growers.',
    start_url: '/dashboard',
    id: '/dashboard',
    display: 'standalone',
    background_color: '#0a0a0a',
    theme_color: '#16a34a',
    orientation: 'portrait-primary',
    scope: '/',
    lang: 'en',
    dir: 'ltr',
    categories: ['productivity', 'business', 'agriculture'],
    icons: [
      {
        src: '/icon-192x192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icon-512x512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/maskable-icon-512x512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'maskable',
      },
      {
        src: '/apple-touch-icon.png',
        sizes: '180x180',
        type: 'image/png',
      },
    ],
    shortcuts: [
      {
        name: 'Cultivation Intelligence',
        short_name: 'Cultivation',
        description: 'View live IoT sensor data and crop health metrics',
        url: '/dashboard?tab=cultivation',
        icons: [{ src: '/icon-192x192.png', sizes: '192x192' }],
      },
      {
        name: 'Leaf Quality Scanner',
        short_name: 'Scanner',
        description: 'AI-powered leaf disease detection and grading',
        url: '/dashboard?tab=leaf-quality',
        icons: [{ src: '/icon-192x192.png', sizes: '192x192' }],
      },
      {
        name: 'Market Intelligence',
        short_name: 'Market',
        description: 'Tea auction prices and AI forecasting',
        url: '/dashboard?tab=market',
        icons: [{ src: '/icon-192x192.png', sizes: '192x192' }],
      },
      {
        name: 'Action Simulator',
        short_name: 'Simulator',
        description: 'Simulate harvest, logistics, and selling strategies',
        url: '/dashboard?tab=action',
        icons: [{ src: '/icon-192x192.png', sizes: '192x192' }],
      },
    ],
  };
}
