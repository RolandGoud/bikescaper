#!/usr/bin/env python3
"""
Bike Scraper - A comprehensive scraper for bike manufacturer websites
"""

import argparse
import logging
import os
import sys
from typing import List, Dict, Any
from datetime import datetime

# Import our modules
from config import MANUFACTURERS, DEFAULT_CONFIG, DEFAULT_OUTPUT_CONFIG
from manufacturers import create_scraper
from utils import DataExporter
from data_models import Bike

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bike_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BikeScraperApp:
    """Main application class for bike scraping"""
    
    def __init__(self):
        self.scraped_bikes: List[Bike] = []
        self.output_config = DEFAULT_OUTPUT_CONFIG
        
    def scrape_manufacturer(self, manufacturer_name: str) -> List[Bike]:
        """Scrape bikes from a specific manufacturer"""
        manufacturer_name = manufacturer_name.lower()
        
        if manufacturer_name not in MANUFACTURERS:
            raise ValueError(f"Unknown manufacturer: {manufacturer_name}")
        
        manufacturer_config = MANUFACTURERS[manufacturer_name]
        logger.info(f"Starting to scrape {manufacturer_config['name']}")
        
        try:
            # Create scraper for the manufacturer
            with create_scraper(manufacturer_name, manufacturer_config) as scraper:
                bikes = scraper.scrape_all_bikes()
                logger.info(f"Successfully scraped {len(bikes)} bikes from {manufacturer_config['name']}")
                return bikes
                
        except Exception as e:
            logger.error(f"Failed to scrape {manufacturer_config['name']}: {str(e)}")
            return []
    
    def scrape_all_manufacturers(self) -> List[Bike]:
        """Scrape bikes from all configured manufacturers"""
        all_bikes = []
        
        for manufacturer_name in MANUFACTURERS.keys():
            try:
                manufacturer_bikes = self.scrape_manufacturer(manufacturer_name)
                all_bikes.extend(manufacturer_bikes)
                logger.info(f"Total bikes scraped so far: {len(all_bikes)}")
                
            except Exception as e:
                logger.error(f"Failed to scrape {manufacturer_name}: {str(e)}")
                continue
        
        return all_bikes
    
    def export_data(self, bikes: List[Bike], output_formats: List[str] = None) -> bool:
        """Export scraped data to various formats"""
        if not bikes:
            logger.warning("No bikes data to export")
            return False
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_config.output_dir, exist_ok=True)
        
        # Default formats if none specified
        if not output_formats:
            output_formats = ['csv', 'json']
        
        success = True
        
        for format_type in output_formats:
            try:
                if format_type.lower() == 'csv':
                    filename = os.path.join(self.output_config.output_dir, self.output_config.csv_filename)
                    DataExporter.export_to_csv(bikes, filename)
                    
                elif format_type.lower() == 'json':
                    filename = os.path.join(self.output_config.output_dir, self.output_config.json_filename)
                    DataExporter.export_to_json(bikes, filename)
                    
                elif format_type.lower() == 'excel':
                    filename = os.path.join(self.output_config.output_dir, self.output_config.excel_filename)
                    DataExporter.export_to_excel(bikes, filename)
                    
                else:
                    logger.warning(f"Unknown export format: {format_type}")
                    
            except Exception as e:
                logger.error(f"Failed to export to {format_type}: {str(e)}")
                success = False
        
        return success
    
    def print_summary(self, bikes: List[Bike]):
        """Print a summary of scraped data"""
        if not bikes:
            print("No bikes were scraped.")
            return
        
        print(f"\n{'='*60}")
        print(f"BIKE SCRAPING SUMMARY")
        print(f"{'='*60}")
        print(f"Total bikes scraped: {len(bikes)}")
        
        # Group by manufacturer
        manufacturer_counts = {}
        category_counts = {}
        
        for bike in bikes:
            # Count by manufacturer
            manufacturer_counts[bike.manufacturer] = manufacturer_counts.get(bike.manufacturer, 0) + 1
            
            # Count by category
            if bike.category:
                category_counts[bike.category] = category_counts.get(bike.category, 0) + 1
        
        print(f"\nBy Manufacturer:")
        for manufacturer, count in sorted(manufacturer_counts.items()):
            print(f"  {manufacturer}: {count} bikes")
        
        if category_counts:
            print(f"\nBy Category:")
            for category, count in sorted(category_counts.items()):
                print(f"  {category}: {count} bikes")
        
        # Price statistics
        prices = [bike.pricing.price for bike in bikes if bike.pricing.price]
        if prices:
            print(f"\nPrice Statistics:")
            print(f"  Average price: ${sum(prices) / len(prices):.2f}")
            print(f"  Min price: ${min(prices):.2f}")
            print(f"  Max price: ${max(prices):.2f}")
            print(f"  Bikes with pricing: {len(prices)}/{len(bikes)}")
        
        print(f"\nScraping completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Scrape bike data from manufacturer websites')
    
    parser.add_argument(
        '--manufacturers', '-m',
        nargs='+',
        choices=list(MANUFACTURERS.keys()) + ['all'],
        default='all',
        help='Manufacturers to scrape (default: all)'
    )
    
    parser.add_argument(
        '--output-formats', '-f',
        nargs='+',
        choices=['csv', 'json', 'excel'],
        default=['csv', 'json'],
        help='Output formats (default: csv json)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default='data',
        help='Output directory (default: data)'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Limit number of bikes to scrape per manufacturer (for testing)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--list-manufacturers',
        action='store_true',
        help='List available manufacturers and exit'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # List manufacturers if requested
    if args.list_manufacturers:
        print("Available manufacturers:")
        for key, config in MANUFACTURERS.items():
            print(f"  {key}: {config['name']} ({config['base_url']})")
        return
    
    # Initialize app
    app = BikeScraperApp()
    app.output_config.output_dir = args.output_dir
    
    try:
        # Determine which manufacturers to scrape
        if 'all' in args.manufacturers:
            manufacturers_to_scrape = list(MANUFACTURERS.keys())
        else:
            manufacturers_to_scrape = args.manufacturers
        
        logger.info(f"Starting bike scraper for manufacturers: {', '.join(manufacturers_to_scrape)}")
        
        all_bikes = []
        
        # Scrape each manufacturer
        for manufacturer in manufacturers_to_scrape:
            try:
                bikes = app.scrape_manufacturer(manufacturer)
                all_bikes.extend(bikes)
                
            except Exception as e:
                logger.error(f"Failed to scrape {manufacturer}: {str(e)}")
                continue
        
        # Export data
        if all_bikes:
            logger.info("Exporting scraped data...")
            app.export_data(all_bikes, args.output_formats)
            
            # Print summary
            app.print_summary(all_bikes)
            
        else:
            logger.warning("No bikes were scraped from any manufacturer")
    
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
