import { z, defineCollection } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    draft: z.boolean().default(false),
  }),
});

const plants = defineCollection({
  type: 'content',
  schema: z.object({
    scientific_name: z.string(),
  }),
});

export const collections = { blog, plants };
