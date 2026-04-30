import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';

export default defineConfig({
  site: 'https://quaintcabeza.github.io',
  base: '/tbh-blog',
  output: 'static',
  integrations: [mdx(), react()],
});
