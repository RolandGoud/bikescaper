# Configuration file for bike scraper
import os
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class ScrapingConfig:
    """Configuration for scraping parameters"""
    delay_between_requests: float = 1.0
    max_retries: int = 3
    timeout: int = 30
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    use_proxy: bool = False
    proxy_list: List[str] = None

@dataclass
class OutputConfig:
    """Configuration for output settings"""
    output_dir: str = "data"
    csv_filename: str = "bikes_data.csv"
    json_filename: str = "bikes_data.json"
    excel_filename: str = "bikes_data.xlsx"
    include_images: bool = True
    image_dir: str = "images"

# Manufacturer URLs and configurations
MANUFACTURERS = {
    "trek": {
        "name": "Trek",
        "base_url": "https://www.trekbikes.com/nl/nl_NL/",
        "bikes_url": "https://www.trekbikes.com/nl/nl_NL/fietsen/",
        "categories": ["racefietsen", "mountainbikes", "elektrische-fietsen", "gravelfietsen", "stads-en-toerfietsen", "kinderfietsen"],
        "requires_selenium": True
    },
    "specialized": {
        "name": "Specialized",
        "base_url": "https://www.specialized.com",
        "bikes_url": "https://www.specialized.com/nl/nl/shop/fietsen",
        "categories": ["racefietsen", "mountainbikes", "elektrische-fietsen", "gravelfietsen", "stads-en-toerfietsen", "kinderfietsen"],
        "requires_selenium": True
    },
    "giant": {
        "name": "Giant",
        "base_url": "https://www.giant-bicycles.com",
        "bikes_url": "https://www.giant-bicycles.com/nl",
        "categories": ["racefietsen", "mountainbikes", "elektrische-fietsen", "gravelfietsen", "stads-en-toerfietsen", "kinderfietsen"],
        "requires_selenium": False
    },
    "cannondale": {
        "name": "Cannondale",
        "base_url": "https://www.cannondale.com",
        "bikes_url": "https://www.cannondale.com/nl-nl/bikes",
        "categories": ["racefietsen", "mountainbikes", "elektrische-fietsen", "gravelfietsen", "stads-en-toerfietsen", "kinderfietsen"],
        "requires_selenium": True
    },
    "canyon": {
        "name": "Canyon",
        "base_url": "https://www.canyon.com/nl-nl/",
        "bikes_url": "https://www.canyon.com/nl-nl/",
        "categories": ["racefietsen", "mountainbikes", "elektrische-fietsen", "gravelfietsen", "stads-en-toerfietsen", "kinderfietsen"],
        "requires_selenium": True
    }
}

# Fields to scrape for each bike
BIKE_FIELDS = [
    "manufacturer",
    "model",
    "category",
    "subcategory",
    "price",
    "currency",
    "frame_material",
    "wheel_size",
    "gears",
    "weight",
    "color_options",
    "sizes_available",
    "description",
    "specifications",
    "images",
    "url",
    "availability",
    "year",
    "rating",
    "reviews_count"
]

# Default scraping configuration
DEFAULT_CONFIG = ScrapingConfig()
DEFAULT_OUTPUT_CONFIG = OutputConfig()

# Environment variables
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_CONFIG.output_dir)
