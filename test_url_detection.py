#!/usr/bin/env python3

import sys
sys.path.append('.')

from manufacturers import TrekScraper, CannondaleScraper
from config import MANUFACTURERS

def test_trek_urls():
    print("=== Testing Trek URL Detection ===")
    trek_config = MANUFACTURERS['trek']
    scraper = TrekScraper(trek_config)
    
    # Test URLs that should be detected as bike detail pages
    valid_urls = [
        '/us/en_US/bikes/electra-bikes/cruiser-bikes/super-deluxe-tandem-7i/p/24579/',
        '/us/en_US/bikes/mountain-bikes/trail-mountain-bikes/fuel-ex-9-8/p/35021/',
        '/us/en_US/bikes/road-bikes/racing-road-bikes/madone-sl-7/p/35023/',
        '/us/en_US/bikes/hybrid-bikes/fitness-bikes/fx-3-disc/p/35021/'
    ]
    
    # Test URLs that should NOT be detected as bike detail pages
    invalid_urls = [
        '/us/en_US/bikes/road-bikes/',
        '/us/en_US/bikes/mountain-bikes/',
        '/us/en_US/bikes/road-bikes/racing-road-bikes/',
        '/us/en_US/c/B100/',
        '/us/en_US/accessories/'
    ]
    
    print("\nValid URLs (should return True):")
    for url in valid_urls:
        result = scraper._is_trek_bike_detail_url(url)
        print(f"  {url}: {result}")
    
    print("\nInvalid URLs (should return False):")
    for url in invalid_urls:
        result = scraper._is_trek_bike_detail_url(url)
        print(f"  {url}: {result}")

def test_cannondale_urls():
    print("\n=== Testing Cannondale URL Detection ===")
    cannondale_config = MANUFACTURERS['cannondale']
    scraper = CannondaleScraper(cannondale_config)
    
    # Test URLs that should be detected as bike detail pages
    valid_urls = [
        '/en-us/bikes/road/race/supersix-evo-carbon-disc-force-etap-axs',
        '/en-us/bikes/mountain/trail/habit-carbon-3',
        '/en-us/bikes/electric/e-road/synapse-neo-carbon-1-rvs',
        '/en-us/bikes/gravel/topstone-carbon-lefty-3'
    ]
    
    # Test URLs that should NOT be detected as bike detail pages
    invalid_urls = [
        '/en-us/bikes/road',
        '/en-us/bikes/mountain',
        '/en-us/bikes/road/race',
        '/en-us/bikes/electric',
        '/en-us/accessories'
    ]
    
    print("\nValid URLs (should return True):")
    for url in valid_urls:
        result = scraper._is_cannondale_bike_detail_url(url)
        print(f"  {url}: {result}")
    
    print("\nInvalid URLs (should return False):")
    for url in invalid_urls:
        result = scraper._is_cannondale_bike_detail_url(url)
        print(f"  {url}: {result}")

if __name__ == "__main__":
    test_trek_urls()
    test_cannondale_urls()
    print("\n=== URL Detection Tests Complete ===") 