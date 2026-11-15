"""Places and exposure: gazetteer, point lookup and exposure under a raster mask."""
from pathlib import Path

PLACES_DIR = Path(__file__).resolve().parents[2] / 'data' / 'cache' / 'places'
RAW_DIR = Path(__file__).resolve().parents[2] / 'data' / 'raw' / 'places'
STUDY_AREA_ID = 'camanava_2026'
BBOX = (120.88, 14.60, 121.04, 14.82)  # W, S, E, N (WGS84)
STUDY_CITY_CODES = ('PH1307501', 'PH1307502', 'PH1307503', 'PH1307504',  # Caloocan, Malabon, Navotas, Valenzuela
                    'PH0301414', 'PH0301412', 'PH0301411')               # Obando, Meycauayan, Marilao

FILES = {
    'city': 'boundaries_city.geojson',
    'barangay': 'boundaries_barangay.geojson',
    'gazetteer': 'gazetteer.json',
    'population': 'worldpop_phl_2020_constrained_clip.tif',
    'landcover': 'esa_worldcover_2021_clip.tif',
    'buildings': 'buildings_osm_centroids.parquet',
    'manifest': 'manifest.json',
}


def path_for(key, root=None):
    return Path(root or PLACES_DIR) / FILES[key]
