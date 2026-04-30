# tbh-blog
We have a bee in our bonnet over native plants at The Brick House

## Local Development

```bash
npm install
npm run dev
```

Open http://localhost:4321/tbh-blog

## Plant Database

The plant database is managed via `scripts/plantsdb.py`. It scrapes plant data from npsot.org and wildflower.org, calculates derived fields, and creates stub MDX profile pages.

### Setup

```bash
cd scripts
python3 -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4
```

### Usage

Add a single plant:
```bash
python3 plantsdb.py "Salvia farinacea"
```

Add multiple plants:
```bash
python3 plantsdb.py "Salvia farinacea, Echinacea purpurea, Malvaviscus arboreus var. drummondii"
```

Add plants from a CSV file (must have `scientific_name` column):
```bash
python3 plantsdb.py --csv plants_to_add.csv
```

Recalculate derived fields for all plants (no scraping):
```bash
python3 plantsdb.py --refresh
```

Re-scrape and recalculate all plants:
```bash
python3 plantsdb.py --refresh --rescrape
```

### Output

- `public/data/plantsdb.csv` - Plant database sorted by scientific name
- `public/data/plantsdb_errors.csv` - Any errors that occurred during processing
- `src/content/plants/[slug]/index.mdx` - Stub profile pages for each plant
