import type { ParsedPlant } from './plants';

// Month abbreviations for display
export const MONTH_ABBREV = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
export const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Size categories
export type SizeCategory = 'XS' | 'S' | 'M' | 'L' | 'XL' | 'XXL';

export const SIZE_LABELS: Record<SizeCategory, string> = {
  'XS': 'Extra Small',
  'S': 'Small',
  'M': 'Medium',
  'L': 'Large',
  'XL': 'Extra Large',
  'XXL': 'Tree',
};

// Light requirement types
export type LightRequirement = 'Sun' | 'Part Shade' | 'Shade';

/**
 * Format height/spread range for display
 */
export function formatSizeRange(min: number | null, max: number | null): string {
  if (min === null && max === null) return '';
  if (min === max || min === null) return `${max}ft`;
  if (max === null) return `${min}ft`;
  return `${min}-${max}ft`;
}

/**
 * Format dimensions for display (e.g., "3ft × 4ft")
 */
export function formatDimensions(plant: ParsedPlant): string {
  const height = plant.avg_height;
  const spread = plant.avg_spread;
  if (height === null && spread === null) return '';
  return `${height ?? '?'}ft × ${spread ?? '?'}ft`;
}

/**
 * Check if plant has a specific light requirement
 */
export function hasLightRequirement(plant: ParsedPlant, light: LightRequirement): boolean {
  return plant.light_requirement.some(l =>
    l.toLowerCase().includes(light.toLowerCase())
  );
}

/**
 * Normalize light requirements to standard categories
 */
export function normalizeLightRequirements(plant: ParsedPlant): LightRequirement[] {
  const normalized: LightRequirement[] = [];

  for (const light of plant.light_requirement) {
    const lower = light.toLowerCase();
    if (lower === 'sun' || lower === 'full sun') {
      if (!normalized.includes('Sun')) normalized.push('Sun');
    } else if (lower.includes('part shade') || lower.includes('partial shade') || lower.includes('dappled')) {
      if (!normalized.includes('Part Shade')) normalized.push('Part Shade');
    } else if (lower === 'shade' || lower === 'full shade') {
      if (!normalized.includes('Shade')) normalized.push('Shade');
    }
  }

  return normalized;
}

/**
 * Get primary bloom color (first color in list)
 */
export function getPrimaryBloomColor(plant: ParsedPlant): string {
  return plant.bloom_color[0] || 'White';
}

/**
 * Map bloom color names to CSS colors
 */
export function getBloomColorCSS(color: string): string {
  const colorMap: Record<string, string> = {
    'Red': '#c9302c',
    'Pink': '#e8749a',
    'Purple': '#6b2d8b',
    'Blue': '#3b5998',
    'White': '#d4d4d4',
    'Yellow': '#f2c94c',
    'Orange': '#d95f2b',
    'Green': '#5a8f3d',
  };
  return colorMap[color] || '#d4d4d4';
}

/**
 * Check if a month is in the bloom period
 */
export function isBloomMonth(plant: ParsedPlant, monthIndex: number): boolean {
  return plant.bloom_period.includes(monthIndex);
}

/**
 * Get bloom period as human-readable string
 */
export function formatBloomPeriod(plant: ParsedPlant): string {
  if (plant.bloom_period.length === 0) return '';
  if (plant.bloom_period.length === 12) return 'Year-round';

  const months = plant.bloom_period.map(i => MONTH_NAMES[i]);

  // Check for continuous range
  const isContiguous = plant.bloom_period.every((m, i) =>
    i === 0 || m === plant.bloom_period[i - 1] + 1
  );

  if (isContiguous && months.length > 2) {
    return `${months[0]} – ${months[months.length - 1]}`;
  }

  return months.join(', ');
}

/**
 * Sort plants by water (ascending), then light (sun first), then size
 */
export function sortPlantsDefault(plants: ParsedPlant[]): ParsedPlant[] {
  return [...plants].sort((a, b) => {
    // Water drops (ascending)
    const waterA = a.water_drops ?? 99;
    const waterB = b.water_drops ?? 99;
    if (waterA !== waterB) return waterA - waterB;

    // Light (sun plants first)
    const hasSunA = hasLightRequirement(a, 'Sun') ? 0 : 1;
    const hasSunB = hasLightRequirement(b, 'Sun') ? 0 : 1;
    if (hasSunA !== hasSunB) return hasSunA - hasSunB;

    // Size (small to large)
    const sizeOrder: Record<string, number> = { 'XS': 0, 'S': 1, 'M': 2, 'L': 3, 'XL': 4, 'XXL': 5 };
    const sizeA = sizeOrder[a.size] ?? 99;
    const sizeB = sizeOrder[b.size] ?? 99;
    return sizeA - sizeB;
  });
}
