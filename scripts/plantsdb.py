#!/usr/bin/env python3
"""
Manage the plant database: scrape data, calculate derived fields, create profile pages.

Usage:
    python3 plantsdb.py "Salvia farinacea"
    python3 plantsdb.py "Salvia farinacea, Echinacea purpurea"
    python3 plantsdb.py --csv plants_to_add.csv
    python3 plantsdb.py --refresh
    python3 plantsdb.py --refresh --rescrape

Options:
    --csv FILE      Read scientific names from a CSV file with 'scientific_name' column
    --rescrape      Re-fetch data from websites even if plant already exists
    --refresh       Recalculate derived fields for all existing plants

Dependencies:
    pip install requests beautifulsoup4
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
PLANTSDB_CSV = REPO_ROOT / "public" / "data" / "plantsdb.csv"
ERRORS_CSV = REPO_ROOT / "public" / "data" / "plantsdb_errors.csv"
PLANTS_CONTENT_DIR = REPO_ROOT / "src" / "content" / "plants"

# Scraped fields
SCRAPED_FIELDS = [
    "scientific_name",
    "common_names",
    "duration",
    "habit",
    "min_height",
    "max_height",
    "min_spread",
    "max_spread",
    "bloom_color",
    "bloom_period",
    "light_requirement",
    "water_use",
    "soil_moisture",
    "soil",
    "wildflower_url",
    "npsot_url",
]

# Calculated fields
CALCULATED_FIELDS = [
    "preferred_name",
    "avg_height",
    "avg_spread",
    "size",
    "water_drops",
]

# Override fields (user can manually set these)
OVERRIDE_FIELDS = [
    "override_preferred_name",
    "override_bloom_color",
    "override_bloom_period",
    "override_light_requirement",
    "override_water_drops",
    "override_size",
]

# Manual fields (set to empty for new plants, preserved for existing)
MANUAL_FIELDS = [
    "descriptors",
    "categories",
]

CSV_FIELDNAMES = SCRAPED_FIELDS + CALCULATED_FIELDS + OVERRIDE_FIELDS + MANUAL_FIELDS

# Plant profile sections - loaded from src/data/plant-sections.json
PLANT_SECTIONS_FILE = REPO_ROOT / "src" / "data" / "plant-sections.json"

# npsot soil types that describe moisture rather than texture
SOIL_MOISTURE_TERMS = {"dry", "moist", "wet", "well drained", "mesic"}

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
})

WILDFLOWER_SEARCH = "https://www.wildflower.org/plants/search.php"
WILDFLOWER_PROFILE = "https://www.wildflower.org/plants/result.php"
NPSOT_BASE = "https://www.npsot.org/posts/native-plant"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_semicolons(value: str) -> str:
    """Normalize a comma-separated value to semicolon-separated."""
    parts = [" ".join(p.split()) for p in value.split(",") if p.strip()]
    return ";".join(parts)


def make_npsot_url(scientific_name: str) -> str:
    """Construct the npsot.org profile URL from a scientific name."""
    slug = scientific_name.strip().lower()
    slug = slug.replace(".", "")
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return f"{NPSOT_BASE}/{slug}/"


def make_plant_slug(scientific_name: str) -> str:
    """Create a URL-safe slug from scientific name."""
    slug = scientific_name.strip().lower()
    slug = slug.replace(".", "")
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug


def parse_height_range(height_str: str) -> tuple[Optional[float], Optional[float]]:
    """Parse '2-6' or '3' into (min, max) floats."""
    if not height_str:
        return None, None
    if "-" in height_str:
        parts = height_str.split("-")
        try:
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            return None, None
    try:
        val = float(height_str)
        return val, val
    except ValueError:
        return None, None


# ---------------------------------------------------------------------------
# Calculated fields
# ---------------------------------------------------------------------------

def calculate_preferred_name(data: dict) -> str:
    """First common name, or scientific name if no common names."""
    common = data.get("common_names", "")
    if common:
        return common.split(";")[0].strip()
    return data.get("scientific_name", "")


def calculate_avg_height(data: dict) -> Optional[int]:
    """Average of min/max height, rounded to nearest int."""
    min_h = data.get("min_height")
    max_h = data.get("max_height")
    try:
        min_val = float(min_h) if min_h else None
        max_val = float(max_h) if max_h else None
    except ValueError:
        return None

    if min_val is not None and max_val is not None:
        return round((min_val + max_val) / 2)
    elif max_val is not None:
        return round(max_val)
    elif min_val is not None:
        return round(min_val)
    return None


def calculate_avg_spread(data: dict) -> Optional[int]:
    """Average of min/max spread, rounded to nearest int."""
    min_s = data.get("min_spread")
    max_s = data.get("max_spread")
    try:
        min_val = float(min_s) if min_s else None
        max_val = float(max_s) if max_s else None
    except ValueError:
        return None

    if min_val is not None and max_val is not None:
        return round((min_val + max_val) / 2)
    elif max_val is not None:
        return round(max_val)
    elif min_val is not None:
        return round(min_val)
    return None


def calculate_size(data: dict) -> str:
    """
    Size category based on avg_height and habit:
    XS = ground cover
    S = up to 2ft
    M = up to 4ft
    L = shrub over 4ft
    XL = tree up to 15ft
    XXL = tree above 15ft
    """
    habit = (data.get("habit") or "").lower()
    avg_h = data.get("avg_height")

    if avg_h is None:
        try:
            avg_h = calculate_avg_height(data)
        except:
            pass

    if avg_h is None:
        return ""

    try:
        avg_h = float(avg_h)
    except (ValueError, TypeError):
        return ""

    # Ground cover
    if "groundcover" in habit.replace(" ", "") or "ground cover" in habit:
        return "XS"

    # Trees
    if "tree" in habit:
        if avg_h > 15:
            return "XXL"
        return "XL"

    # Everything else by height
    if avg_h <= 2:
        return "S"
    elif avg_h <= 4:
        return "M"
    else:
        return "L"


def calculate_water_drops(data: dict) -> Optional[int]:
    """
    Water drops based on water_use:
    very low = 0, low = 1, medium = 2, high = 3
    """
    water = (data.get("water_use") or "").lower()

    if not water:
        return None

    # Take first value if multiple
    water = water.split(";")[0].strip()

    if "very low" in water:
        return 0
    elif "low" in water:
        return 1
    elif "medium" in water or "moderate" in water:
        return 2
    elif "high" in water:
        return 3
    return None


def calculate_all_fields(data: dict) -> dict:
    """Calculate all derived fields and add to data dict."""
    data["preferred_name"] = calculate_preferred_name(data)

    avg_h = calculate_avg_height(data)
    data["avg_height"] = avg_h if avg_h is not None else ""

    avg_s = calculate_avg_spread(data)
    data["avg_spread"] = avg_s if avg_s is not None else ""

    data["size"] = calculate_size(data)

    wd = calculate_water_drops(data)
    data["water_drops"] = wd if wd is not None else ""

    return data


# ---------------------------------------------------------------------------
# Scraping: wildflower.org
# ---------------------------------------------------------------------------

def search_wildflower(name: str) -> tuple[str, list[dict]]:
    """
    Search wildflower.org for a plant name.
    Returns (usda_symbol, candidates).
    """
    resp = SESSION.get(
        WILDFLOWER_SEARCH,
        params={"search_field": name, "newsearch": "true"},
        timeout=20,
    )
    resp.raise_for_status()

    if "result.php" in resp.url and "id_plant=" in resp.url:
        symbol = resp.url.split("id_plant=")[-1].split("&")[0]
        return symbol, []

    soup = BeautifulSoup(resp.text, "html.parser")
    candidates = []
    table = soup.find("table", attrs={"border": "0", "cellpadding": "5"})
    if table:
        for row in table.find_all("tr"):
            link = row.find("a", href=lambda h: h and "result.php?id_plant=" in h)
            if not link:
                continue
            symbol = link["href"].split("id_plant=")[-1].split("&")[0]
            sci = link.get_text(" ", strip=True)
            tds = row.find_all("td")
            common = tds[1].get_text(", ", strip=True) if len(tds) > 1 else ""
            candidates.append({
                "usda_symbol": symbol,
                "scientific_name": sci,
                "common_name": common,
            })

    if len(candidates) == 1:
        return candidates[0]["usda_symbol"], []
    return "", candidates


def _wf_field(soup: BeautifulSoup, label: str) -> str:
    """Extract the value after <strong>label:</strong> on a wildflower.org page."""
    strong = soup.find("strong", string=f"{label}:")
    if not strong:
        return ""
    parts = []
    for sib in strong.next_siblings:
        if isinstance(sib, Tag):
            if sib.name in ("br", "strong"):
                break
            parts.append(sib.get_text(" ", strip=True))
        elif isinstance(sib, NavigableString):
            t = str(sib).strip()
            if t:
                parts.append(t)
    return " ".join(parts).strip().strip(",").strip()


def fetch_wildflower_profile(usda_symbol: str) -> dict:
    """Fetch wildflower.org profile data."""
    url = f"{WILDFLOWER_PROFILE}?id_plant={usda_symbol}"
    resp = SESSION.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = {"wildflower_url": url}

    sn_tag = soup.find("h2", class_="tax_sn")
    if sn_tag:
        data["scientific_name"] = sn_tag.get_text(" ", strip=True)

    for section in soup.find_all("div", class_="section"):
        heading = section.find("h4")
        if heading and "Bloom Information" in heading.text:
            bt = _wf_field(section, "Bloom Time")
            if bt:
                data["bloom_period"] = to_semicolons(bt)
            break

    return data


# ---------------------------------------------------------------------------
# Scraping: npsot.org
# ---------------------------------------------------------------------------

def _npsot_id(soup: BeautifulSoup, element_id: str) -> str:
    tag = soup.find(id=element_id)
    return tag.get_text(" ", strip=True) if tag else ""


def fetch_npsot_profile(npsot_url: str) -> Optional[dict]:
    """Fetch npsot.org plant profile. Returns None if not found."""
    try:
        resp = SESSION.get(npsot_url, timeout=20)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    if not soup.find(id="native-plant-growth-form"):
        return None

    data = {"npsot_url": npsot_url}

    common = _npsot_id(soup, "native-plant-common-name")
    other = _npsot_id(soup, "native-plant-other-common")
    all_names = [common] + [n.strip() for n in other.split(",") if n.strip()] if other else ([common] if common else [])
    if all_names:
        data["common_names"] = ";".join(all_names)

    sci = _npsot_id(soup, "native-plant-botanical-name")
    if sci:
        data["scientific_name"] = sci

    data["habit"] = _npsot_id(soup, "native-plant-growth-form")
    data["duration"] = _npsot_id(soup, "native-plant-lifespan")

    h_min = _npsot_id(soup, "native-plant-height-min")
    h_max = _npsot_id(soup, "native-plant-height-max")
    if h_min:
        data["min_height"] = h_min
    if h_max:
        data["max_height"] = h_max

    s_min = _npsot_id(soup, "native-plant-spread-min")
    s_max = _npsot_id(soup, "native-plant-spread-max")
    if s_min:
        data["min_spread"] = s_min
    if s_max:
        data["max_spread"] = s_max

    data["light_requirement"] = to_semicolons(_npsot_id(soup, "native-plant-light-requirement"))
    data["water_use"] = to_semicolons(_npsot_id(soup, "native-plant-water-requirement"))
    data["bloom_color"] = to_semicolons(_npsot_id(soup, "native-plant-bloom-color"))

    soil_raw = _npsot_id(soup, "native-plant-soil-types")
    if soil_raw:
        moisture_parts, texture_parts = [], []
        for part in (p.strip() for p in soil_raw.split(",") if p.strip()):
            if part.lower() in SOIL_MOISTURE_TERMS:
                moisture_parts.append(part)
            else:
                texture_parts.append(part)
        if moisture_parts:
            data["soil_moisture"] = ";".join(moisture_parts)
        if texture_parts:
            data["soil"] = ";".join(texture_parts)

    return data


# ---------------------------------------------------------------------------
# Scrape plant data
# ---------------------------------------------------------------------------

def scrape_plant(scientific_name: str) -> dict:
    """
    Scrape plant data from npsot.org (primary) and wildflower.org (fallback/supplement).
    Returns a dict with scraped fields.
    """
    data = {"scientific_name": scientific_name}

    # Try npsot first
    npsot_url = make_npsot_url(scientific_name)
    npsot_data = fetch_npsot_profile(npsot_url)

    if npsot_data:
        data.update(npsot_data)

    # Search wildflower.org for bloom period and URL
    try:
        usda_symbol, candidates = search_wildflower(scientific_name)

        if usda_symbol:
            wf_data = fetch_wildflower_profile(usda_symbol)
            # Only add wildflower data if not already present from npsot
            for key, val in wf_data.items():
                if key not in data or not data[key]:
                    data[key] = val
        elif candidates:
            # Try the first candidate
            wf_data = fetch_wildflower_profile(candidates[0]["usda_symbol"])
            for key, val in wf_data.items():
                if key not in data or not data[key]:
                    data[key] = val
    except requests.RequestException:
        pass  # Continue without wildflower data

    # Ensure npsot_url is set
    if "npsot_url" not in data:
        data["npsot_url"] = npsot_url

    return data


# ---------------------------------------------------------------------------
# CSV operations
# ---------------------------------------------------------------------------

def load_plantsdb() -> dict[str, dict]:
    """Load existing plants from CSV, keyed by scientific_name."""
    plants = {}
    if not PLANTSDB_CSV.exists():
        return plants

    with PLANTSDB_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sci_name = row.get("scientific_name", "").strip()
            if sci_name:
                plants[sci_name] = row
    return plants


def save_plantsdb(plants: dict[str, dict]) -> None:
    """Save plants to CSV, sorted by scientific_name."""
    PLANTSDB_CSV.parent.mkdir(parents=True, exist_ok=True)

    sorted_plants = sorted(plants.values(), key=lambda p: p.get("scientific_name", "").lower())

    with PLANTSDB_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for plant in sorted_plants:
            writer.writerow({k: plant.get(k, "") for k in CSV_FIELDNAMES})


def save_errors(errors: list[dict]) -> None:
    """Save errors to CSV."""
    if not errors:
        return

    ERRORS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with ERRORS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["scientific_name", "error"])
        writer.writeheader()
        writer.writerows(errors)


# ---------------------------------------------------------------------------
# MDX page generation
# ---------------------------------------------------------------------------

def load_profile_sections() -> list[str]:
    """Load profile sections from src/data/plant-sections.json."""
    if not PLANT_SECTIONS_FILE.exists():
        print(f"Warning: {PLANT_SECTIONS_FILE} not found, using empty sections", file=sys.stderr)
        return []

    with PLANT_SECTIONS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("sections", [])


def create_plant_page(scientific_name: str) -> bool:
    """
    Create a stub MDX page for a plant if it doesn't exist.
    Returns True if page was created, False if it already exists.
    """
    slug = make_plant_slug(scientific_name)
    plant_dir = PLANTS_CONTENT_DIR / slug
    mdx_file = plant_dir / "index.mdx"

    if mdx_file.exists():
        return False

    plant_dir.mkdir(parents=True, exist_ok=True)
    images_dir = plant_dir / "images"
    images_dir.mkdir(exist_ok=True)

    sections = load_profile_sections()

    # Create stub MDX with empty sections
    content = f"""---
scientific_name: "{scientific_name}"
---

"""
    for section in sections:
        content += f"## {section}\n\n"

    mdx_file.write_text(content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_plant(scientific_name: str, existing: Optional[dict], rescrape: bool) -> tuple[dict, Optional[str]]:
    """
    Process a single plant: scrape if needed, calculate fields.
    Returns (plant_data, error_message).
    """
    scientific_name = scientific_name.strip()

    if existing and not rescrape:
        # Just recalculate derived fields
        data = existing.copy()
    else:
        # Scrape fresh data
        try:
            data = scrape_plant(scientific_name)
        except Exception as e:
            return {}, f"Scrape failed: {str(e)}"

        # Preserve manual and override fields from existing
        if existing:
            for field in MANUAL_FIELDS + OVERRIDE_FIELDS:
                if existing.get(field):
                    data[field] = existing[field]

    # Calculate derived fields
    data = calculate_all_fields(data)

    # For new plants, set override fields to corresponding scraped/calculated values
    if not existing:
        # Initialize manual fields to empty
        for field in MANUAL_FIELDS:
            data[field] = ""
        # Set override fields to their source values
        override_mappings = {
            "override_preferred_name": "preferred_name",
            "override_bloom_color": "bloom_color",
            "override_bloom_period": "bloom_period",
            "override_light_requirement": "light_requirement",
            "override_water_drops": "water_drops",
            "override_size": "size",
        }
        for override_field, source_field in override_mappings.items():
            data[override_field] = data.get(source_field, "")

    return data, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the plant database")
    parser.add_argument("names", nargs="?", help="Scientific names (comma-separated)")
    parser.add_argument("--csv", dest="csv_file", help="CSV file with scientific_name column")
    parser.add_argument("--rescrape", action="store_true", help="Re-fetch data from websites")
    parser.add_argument("--refresh", action="store_true", help="Recalculate fields for all plants")

    args = parser.parse_args()

    # Collect scientific names to process
    names_to_process = []

    if args.refresh:
        # Process all existing plants
        plants = load_plantsdb()
        names_to_process = list(plants.keys())
        print(f"Refreshing {len(names_to_process)} existing plants...")
    elif args.csv_file:
        csv_path = Path(args.csv_file)
        if not csv_path.exists():
            print(f"Error: CSV file not found: {args.csv_file}", file=sys.stderr)
            sys.exit(1)
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("scientific_name", "").strip()
                if name:
                    names_to_process.append(name)
        print(f"Processing {len(names_to_process)} plants from {args.csv_file}...")
    elif args.names:
        names_to_process = [n.strip() for n in args.names.split(",") if n.strip()]
        print(f"Processing {len(names_to_process)} plants...")
    else:
        parser.print_help()
        sys.exit(1)

    # Load existing data
    plants = load_plantsdb()
    errors = []
    new_pages = 0

    for i, name in enumerate(names_to_process):
        print(f"  [{i+1}/{len(names_to_process)}] {name}...", end=" ", flush=True)

        existing = plants.get(name)
        data, error = process_plant(name, existing, args.rescrape)

        if error:
            print(f"ERROR: {error}")
            errors.append({"scientific_name": name, "error": error})
        else:
            plants[name] = data

            # Create MDX page for new plants
            if not existing or args.rescrape:
                if create_plant_page(name):
                    new_pages += 1
                    print("OK (page created)")
                else:
                    print("OK")
            else:
                print("OK")

        # Rate limiting
        if i < len(names_to_process) - 1:
            time.sleep(2)

    # Save results
    save_plantsdb(plants)
    save_errors(errors)

    print(f"\nDone! {len(plants)} plants in database.")
    if new_pages:
        print(f"  Created {new_pages} new plant pages.")
    if errors:
        print(f"  {len(errors)} errors written to {ERRORS_CSV}")


if __name__ == "__main__":
    main()
