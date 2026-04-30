import { z } from 'zod';
import Papa from 'papaparse';
import { readFileSync } from 'fs';
import { join } from 'path';

// Schema for plant data from plantsdb.csv
export const PlantSchema = z.object({
  scientific_name: z.string(),
  common_names: z.string(),
  duration: z.string(),
  habit: z.string(),
  min_height: z.string(),
  max_height: z.string(),
  min_spread: z.string(),
  max_spread: z.string(),
  bloom_color: z.string(),
  bloom_period: z.string(),
  light_requirement: z.string(),
  water_use: z.string(),
  soil_moisture: z.string(),
  soil: z.string(),
  wildflower_url: z.string(),
  npsot_url: z.string(),
  preferred_name: z.string(),
  avg_height: z.string(),
  avg_spread: z.string(),
  size: z.string(),
  water_drops: z.string(),
  override_preferred_name: z.string(),
  override_bloom_color: z.string(),
  override_bloom_period: z.string(),
  override_light_requirement: z.string(),
  override_water_drops: z.string(),
  override_size: z.string(),
  descriptors: z.string(),
  categories: z.string(),
});

export type Plant = z.infer<typeof PlantSchema>;

// Parsed plant with resolved overrides and typed values
export interface ParsedPlant {
  scientific_name: string;
  common_names: string[];
  preferred_name: string;
  duration: string;
  habit: string[];
  min_height: number | null;
  max_height: number | null;
  min_spread: number | null;
  max_spread: number | null;
  avg_height: number | null;
  avg_spread: number | null;
  size: string;
  bloom_color: string[];
  bloom_period: number[]; // month indices 0-11
  light_requirement: string[];
  water_use: string[];
  water_drops: number | null;
  soil_moisture: string[];
  soil: string[];
  wildflower_url: string;
  npsot_url: string;
  descriptors: string[];
  categories: string[];
  slug: string;
}

// Month name to index mapping
const MONTH_MAP: Record<string, number> = {
  'jan': 0, 'feb': 1, 'mar': 2, 'apr': 3, 'may': 4, 'jun': 5,
  'jul': 6, 'aug': 7, 'sep': 8, 'oct': 9, 'nov': 10, 'dec': 11,
};

/**
 * Parse semicolon-separated string into array
 */
export function parseSemicolonList(value: string): string[] {
  if (!value) return [];
  return value.split(';').map(s => s.trim()).filter(Boolean);
}

/**
 * Parse bloom period string into array of month indices (0-11)
 */
export function parseBloomPeriod(bloomPeriod: string): number[] {
  const months = parseSemicolonList(bloomPeriod);
  return months
    .map(m => MONTH_MAP[m.toLowerCase()])
    .filter((idx): idx is number => idx !== undefined)
    .sort((a, b) => a - b);
}

/**
 * Parse numeric string, return null if empty or invalid
 */
function parseNumber(value: string): number | null {
  if (!value) return null;
  const num = parseFloat(value);
  return isNaN(num) ? null : num;
}

/**
 * Create URL-safe slug from scientific name
 */
export function makeSlug(scientificName: string): string {
  return scientificName
    .toLowerCase()
    .replace(/\./g, '')
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

/**
 * Get effective value (override if set, otherwise original)
 */
function getEffective(original: string, override: string): string {
  return override || original;
}

/**
 * Parse raw plant data into typed ParsedPlant
 */
export function parsePlant(raw: Plant): ParsedPlant {
  return {
    scientific_name: raw.scientific_name,
    common_names: parseSemicolonList(raw.common_names),
    preferred_name: getEffective(raw.preferred_name, raw.override_preferred_name),
    duration: raw.duration,
    habit: parseSemicolonList(raw.habit),
    min_height: parseNumber(raw.min_height),
    max_height: parseNumber(raw.max_height),
    min_spread: parseNumber(raw.min_spread),
    max_spread: parseNumber(raw.max_spread),
    avg_height: parseNumber(raw.avg_height),
    avg_spread: parseNumber(raw.avg_spread),
    size: getEffective(raw.size, raw.override_size),
    bloom_color: parseSemicolonList(getEffective(raw.bloom_color, raw.override_bloom_color)),
    bloom_period: parseBloomPeriod(getEffective(raw.bloom_period, raw.override_bloom_period)),
    light_requirement: parseSemicolonList(getEffective(raw.light_requirement, raw.override_light_requirement)),
    water_use: parseSemicolonList(raw.water_use),
    water_drops: parseNumber(getEffective(raw.water_drops, raw.override_water_drops)),
    soil_moisture: parseSemicolonList(raw.soil_moisture),
    soil: parseSemicolonList(raw.soil),
    wildflower_url: raw.wildflower_url,
    npsot_url: raw.npsot_url,
    descriptors: parseSemicolonList(raw.descriptors),
    categories: parseSemicolonList(raw.categories),
    slug: makeSlug(raw.scientific_name),
  };
}

/**
 * Load and parse all plants from plantsdb.csv
 */
export function loadPlants(): ParsedPlant[] {
  const csvPath = join(process.cwd(), 'public', 'data', 'plantsdb.csv');
  const csvText = readFileSync(csvPath, 'utf-8');

  const { data } = Papa.parse<Record<string, string>>(csvText, {
    header: true,
    skipEmptyLines: true,
  });

  return data
    .map(row => {
      const parsed = PlantSchema.safeParse(row);
      if (!parsed.success) {
        console.warn(`Invalid plant data: ${row.scientific_name}`, parsed.error);
        return null;
      }
      return parsePlant(parsed.data);
    })
    .filter((p): p is ParsedPlant => p !== null);
}

/**
 * Get a single plant by slug
 */
export function getPlantBySlug(slug: string): ParsedPlant | undefined {
  const plants = loadPlants();
  return plants.find(p => p.slug === slug);
}

/**
 * Get plants filtered by category
 */
export function getPlantsByCategory(category: string): ParsedPlant[] {
  const plants = loadPlants();
  return plants.filter(p => p.categories.includes(category));
}
