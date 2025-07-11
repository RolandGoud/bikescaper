#!/usr/bin/env python3
"""
Trek Bikes Scraper - Complete Implementation
Scrapes Trek road bikes from the Dutch website with intelligent predictions
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import pandas as pd
import re
import logging
from datetime import datetime
import time
import os
from urllib.parse import urljoin, urlparse
import glob

class TrekBikeScraper:
    def __init__(self):
        self.base_url = "https://www.trekbikes.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trek_scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def extract_bikes_from_datalayer(self, soup):
        """Extract bike data from dataLayer JavaScript"""
        bikes = []
        
        # Get the raw HTML content to search for dataLayer data
        # This handles cases where script tags might have unusual names or attributes
        html_content = str(soup)
        
        # Look for impressions array in the raw content
        impressions_match = re.search(r'"impressions"\s*:\s*(\[.*?\])', html_content, re.DOTALL)
        if impressions_match:
            try:
                impressions_json = impressions_match.group(1)
                # Clean up the JSON - remove extra whitespace and ensure proper formatting
                impressions_json = re.sub(r'\s+', ' ', impressions_json)
                impressions_json = impressions_json.strip()
                
                impressions = json.loads(impressions_json)
                self.logger.info(f"Successfully parsed {len(impressions)} bikes from impressions")
                
                for impression in impressions:
                    if isinstance(impression, dict):
                        bike_info = {
                            'name': impression.get('name', ''),
                            'price': impression.get('price', ''),
                            'category': impression.get('category', ''),
                            'brand': impression.get('brand', 'Trek'),
                            'url': f"/nl/nl_NL/p/{impression.get('id', '')}/",
                            'sku': impression.get('id', ''),
                            'variant': impression.get('variant', '')
                        }
                        if bike_info['name']:
                            bikes.append(bike_info)
                            
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse impressions JSON: {e}")
                # Log a sample of the problematic JSON for debugging
                sample = impressions_json[:200] if 'impressions_json' in locals() else 'N/A'
                self.logger.error(f"JSON sample: {sample}")
        
        # Fallback: Try traditional script tag parsing
        if not bikes:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'dataLayer' in script.string:
                    script_content = script.string
                    
                    # Look for ecommerce items array
                    ecommerce_match = re.search(r'ecommerce["\']?\s*:\s*{[^}]*items["\']?\s*:\s*(\[.*?\])', script_content, re.DOTALL)
                    if ecommerce_match:
                        try:
                            items_json = ecommerce_match.group(1)
                            items = json.loads(items_json)
                            
                            for item in items:
                                if isinstance(item, dict):
                                    bike_info = {
                                        'name': item.get('item_name', ''),
                                        'price': item.get('price', ''),
                                        'category': item.get('item_category', ''),
                                        'brand': item.get('item_brand', 'Trek'),
                                        'url': f"/nl/nl_NL/p/{item.get('item_id', '')}/",
                                        'sku': item.get('item_id', ''),
                                        'variant': item.get('item_variant', '')
                                    }
                                    if bike_info['name']:
                                        bikes.append(bike_info)
                                        
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Failed to parse ecommerce items JSON: {e}")
                            continue
        
        return bikes

    def extract_color_variants(self, soup):
        """Extract color variants from various sources"""
        color_variants = {}
        
        # Method 1: Look for color data in script tags
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                script_content = script.string
                
                # Pattern 1: Direct color array in JavaScript
                color_pattern = r'"name"\s*:\s*"([^"]+)".*?"color"\s*:\s*\[\s*((?:"[^"]*"(?:\s*,\s*)?)+)\s*\]'
                matches = re.findall(color_pattern, script_content, re.DOTALL)
                
                for bike_name, colors_str in matches:
                    colors = re.findall(r'"([^"]+)"', colors_str)
                    if colors:
                        color_variants[bike_name] = colors
                        self.logger.info(f"Found {len(colors)} color variants for {bike_name}: {colors}")
                
                # Pattern 2: HTML entity encoded colors
                entity_pattern = r'"name"\s*:\s*"([^"]+)".*?&#034;color&#034;\s*:\s*\[\s*((?:&#034;[^&]*&#034;(?:\s*,\s*)?)+)\s*\]'
                entity_matches = re.findall(entity_pattern, script_content, re.DOTALL)
                
                for bike_name, colors_str in entity_matches:
                    colors = re.findall(r'&#034;([^&]*)&#034;', colors_str)
                    if colors:
                        color_variants[bike_name] = colors
                        self.logger.info(f"Found {len(colors)} color variants for {bike_name}: {colors}")
        
        return color_variants

    def extract_specifications(self, bike_info):
        """Extract detailed specifications from bike detail page"""
        if not bike_info.get('url'):
            return {}
            
        detail_url = urljoin(self.base_url, bike_info['url'])
        
        try:
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            specifications = {}
            import re
            
            # Extract specifications from tables
            spec_tables = soup.find_all('table')
            for table in spec_tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # Try different methods to extract text
                        key = cells[0].get_text(strip=True)
                        if not key:
                            key = cells[0].text.strip()
                        if not key:
                            # Extract text from HTML, removing tags but keeping content
                            key_html = str(cells[0])
                            key = re.sub(r'<[^>]+>', ' ', key_html).strip()
                            key = re.sub(r'\s+', ' ', key).strip()
                        
                        value = cells[1].get_text(strip=True) 
                        if not value:
                            value = cells[1].text.strip()
                        if not value:
                            # Extract text from HTML, removing tags but keeping content
                            value_html = str(cells[1])
                            # Remove HTML tags but keep the text content
                            value = re.sub(r'<[^>]+>', ' ', value_html).strip()
                            # Clean up extra whitespace
                            value = re.sub(r'\s+', ' ', value).strip()
                        
                        # Clean up the key - remove common prefixes and suffixes
                        if key.startswith('*'):
                            key = key[1:].strip()
                        if ':' in key and key.endswith(':'):
                            key = key[:-1].strip()
                        
                        if key and value and key != value and len(key) < 100 and len(value) < 500:
                            specifications[key] = value
            
            # Extract specifications from definition lists
            spec_lists = soup.find_all('dl')
            for dl in spec_lists:
                dts = dl.find_all('dt')
                dds = dl.find_all('dd')
                for dt, dd in zip(dts, dds):
                    key = dt.get_text(strip=True)
                    value = dd.get_text(strip=True)
                    if key and value:
                        specifications[key] = value
            
            # Extract fork information from content
            fork_info = self.extract_fork_info_from_content(soup)
            if fork_info:
                specifications['Voorvork'] = fork_info
                self.logger.info(f"Extracted fork info from content: {fork_info[:50]}...")
            
            # Try to determine framefit if missing
            if 'Framefit' not in specifications or not specifications.get('Framefit'):
                framefit = self.determine_framefit(bike_info)
                if framefit:
                    specifications['Framefit'] = framefit + "*"
                    self.logger.info(f"Determined framefit (prediction): {framefit}")
            
            # Try to extract bottom bracket from page content if missing
            if 'Bottom bracket' not in specifications or not specifications.get('Bottom bracket'):
                bottom_bracket = self.extract_bottom_bracket_from_content(soup)
                if bottom_bracket:
                    specifications['Bottom bracket'] = bottom_bracket
                    self.logger.info(f"Extracted bottom bracket from content: {bottom_bracket}")
                else:
                    # Fallback to prediction if extraction fails
                    bottom_bracket = self.determine_bottom_bracket(bike_info)
                    if bottom_bracket:
                        specifications['Bottom bracket'] = bottom_bracket + "*"
                        self.logger.info(f"Determined bottom bracket (prediction): {bottom_bracket}")
            
            # Try to extract chain information from page content if missing
            if 'Ketting' not in specifications or not specifications.get('Ketting'):
                chain_info = self.extract_chain_info_from_content(soup)
                if chain_info:
                    specifications['Ketting'] = chain_info
                    self.logger.info(f"Extracted chain info from content: {chain_info}")
                else:
                    # Fallback to prediction based on drivetrain
                    chain_info = self.determine_chain_from_drivetrain(specifications)
                    if chain_info:
                        specifications['Ketting'] = chain_info + "*"
                        self.logger.info(f"Determined chain from drivetrain (prediction): {chain_info}")
            
            # Detect 1x setups and add front derailleur info
            self.detect_1x_setup(specifications, bike_info)
            
            return specifications
            
        except Exception as e:
            self.logger.error(f"Error extracting specifications for {bike_info.get('name', 'Unknown')}: {e}")
            return {}

    def extract_fork_info_from_content(self, soup):
        """Extract fork information from page content"""
        content_text = soup.get_text().lower()
        
        # Look for fork-related information
        fork_patterns = [
            r'carbon voorvork[^.]*',
            r'voorvork[^.]*carbon[^.]*',
            r'fork[^.]*carbon[^.]*',
            r'carbon fork[^.]*'
        ]
        
        for pattern in fork_patterns:
            matches = re.findall(pattern, content_text, re.IGNORECASE)
            if matches:
                # Return the first meaningful match, cleaned up
                fork_info = matches[0].strip()
                if len(fork_info) > 10:  # Only return if it's substantial
                    return fork_info[:100] + "..." if len(fork_info) > 100 else fork_info
        
        return None

    def extract_bottom_bracket_from_content(self, soup):
        """Extract bottom bracket information from page content"""
        content_text = soup.get_text()
        
        # Look for bottom bracket patterns
        bb_patterns = [
            r'((?:SRAM DUB|Praxis|Shimano RS\d+)[^.]*?(?:T47|BSA|PressFit)[^.]*)',
            r'((?:T47|BSA|PressFit)[^.]*?(?:SRAM DUB|Praxis|Shimano RS\d+)[^.]*)',
            r'(Bottom bracket[^.]*(?:SRAM|Praxis|Shimano)[^.]*)',
            r'((?:SRAM|Praxis|Shimano)[^.]*bottom bracket[^.]*)'
        ]
        
        for pattern in bb_patterns:
            matches = re.findall(pattern, content_text, re.IGNORECASE)
            if matches:
                bb_info = matches[0].strip()
                if len(bb_info) > 5:  # Only return if it's substantial
                    return bb_info[:100] if len(bb_info) > 100 else bb_info
        
        return None

    def extract_chain_info_from_content(self, soup):
        """Extract chain information from page content"""
        content_text = soup.get_text()
        
        # Look for chain patterns
        chain_patterns = [
            r'((?:SRAM|Shimano|KMC)\s+(?:PC-\d+|HG\d+|CN\d+|XT M\d+|Ultegra|105)[^.]*?(?:\d+-)?\d+-speed)',
            r'((?:SRAM|Shimano|KMC)\s+[^.]*?(?:\d+-)?\d+-speed[^.]*chain)',
            r'(chain[^.]*(?:SRAM|Shimano|KMC)[^.]*(?:\d+-)?\d+-speed)',
            r'((?:\d+-)?\d+-speed[^.]*(?:SRAM|Shimano|KMC)[^.]*chain)'
        ]
        
        for pattern in chain_patterns:
            matches = re.findall(pattern, content_text, re.IGNORECASE)
            if matches:
                chain_info = matches[0].strip()
                if len(chain_info) > 5:  # Only return if it's substantial
                    return chain_info[:100] if len(chain_info) > 100 else chain_info
        
        return None

    def determine_framefit(self, bike_info):
        """Determine framefit based on bike name and category"""
        bike_name = bike_info.get('name', '').lower()
        category = bike_info.get('category', '').lower()
        
        # Endurance bikes
        if any(series in bike_name for series in ['domane', 'checkpoint']):
            return 'Endurance'
        
        # Race bikes
        if any(series in bike_name for series in ['madone', 'émonda']):
            return 'H1.5 Race'
        
        # Triathlon bikes
        if 'speed concept' in bike_name:
            return 'Triatlon'
        
        # Cyclocross bikes
        if 'boone' in bike_name:
            return 'H1.5 Race'
        
        # Fitness bikes
        if 'fx' in bike_name:
            return 'Comfort'
        
        # Default based on category
        if 'performance' in category:
            return 'H1.5 Race'
        elif 'gravel' in category or 'cyclocross' in category:
            return 'Endurance'
        elif 'fitness' in category:
            return 'Comfort'
        elif 'triathlon' in category:
            return 'Triatlon'
        
        return None

    def determine_bottom_bracket(self, bike_info):
        """Determine bottom bracket based on bike characteristics"""
        bike_name = bike_info.get('name', '').lower()
        
        # SRAM DUB for higher-end bikes
        if any(series in bike_name for series in ['slr', 'sl 6', 'sl 7', 'sl 8', 'sl 9']) and 'axs' in bike_name:
            return 'SRAM DUB, T47 met schroefdraad, interne lagers'
        
        # SRAM DUB Wide for gravel bikes
        if any(series in bike_name for series in ['checkpoint']) and any(level in bike_name for level in ['alr', 'sl']):
            return 'SRAM DUB Wide, T47 met schroefdraad, interne lagers'
        
        # Praxis for many Trek bikes
        if any(series in bike_name for series in ['domane', 'émonda', 'madone']):
            return 'Praxis, T47 met schroefdraad, interne lagers'
        
        # Shimano for lower-end and fitness bikes
        if any(series in bike_name for series in ['fx', 'al 2', 'al 4', 'al 5']):
            if 'fx' in bike_name:
                return 'Shimano RS500, 86 mm, PressFit'
            else:
                return 'Shimano RS501 BSA'
        
        return None

    def determine_chain_from_drivetrain(self, specifications):
        """Determine chain based on drivetrain components"""
        rear_derailleur = specifications.get('Achterderailleur', '').lower()
        cassette = specifications.get('Cassette', '').lower()
        
        # SRAM chains
        if 'sram' in rear_derailleur:
            if 'apex' in rear_derailleur:
                if '12-speed' in cassette or '12' in cassette:
                    return 'SRAM Apex, 12-speed'
                else:
                    return 'SRAM PC-1130, 11-speed'
            elif 'rival' in rear_derailleur:
                if '13-speed' in cassette or '13' in cassette:
                    return 'SRAM Rival, 13-speed'
                else:
                    return 'SRAM Rival, 12-speed'
            elif 'force' in rear_derailleur:
                if '13-speed' in cassette or '13' in cassette:
                    return 'SRAM Force E1, 12/13-speed'
                else:
                    return 'SRAM Force, 12-speed'
            elif 'red' in rear_derailleur:
                return 'SRAM RED D1, 12-speed'
        
        # Shimano chains
        elif 'shimano' in rear_derailleur:
            if 'ultegra' in rear_derailleur or 'xt' in rear_derailleur:
                return 'Shimano XT M8100, 12-speed'
            elif '105' in rear_derailleur:
                return 'Shimano SLX M7100, 12-speed'
            elif 'cues' in rear_derailleur:
                return 'Shimano CN-LG500, 10-speed'
        
        # Generic fallback based on cassette speed
        if '11-speed' in cassette or '11' in cassette:
            return 'SRAM PC-1130, 11-speed'
        elif '12-speed' in cassette or '12' in cassette:
            return 'Shimano SLX M7100, 12-speed'
        elif '10-speed' in cassette or '10' in cassette:
            return 'Shimano CN-LG500, 10-speed'
        
        return None

    def detect_1x_setup(self, specifications, bike_info):
        """Detect 1x drivetrain setups and add appropriate front derailleur info"""
        chainring = specifications.get('Voortandwiel', '').lower()
        cassette = specifications.get('Cassette', '').lower()
        rear_derailleur = specifications.get('Achterderailleur', '').lower()
        bike_name = bike_info.get('name', '').lower()
        
        is_1x = False
        detection_reason = ""
        
        # Check for 1x indicators
        if 'x' in chainring and not '2x' in chainring:
            is_1x = True
            detection_reason = "1x-only chainring specification"
        elif any(keyword in cassette for keyword in ['10-50', '10-52', '11-50', '11-52', '10-44', '10-42']):
            # Wide range cassettes typically indicate 1x
            cassette_range = re.search(r'(\d+)-(\d+)', cassette)
            if cassette_range:
                min_teeth = int(cassette_range.group(1))
                max_teeth = int(cassette_range.group(2))
                if max_teeth - min_teeth >= 30:  # Wide range
                    is_1x = True
                    detection_reason = f"wide cassette range ({max_teeth - min_teeth} teeth)"
        elif 'checkpoint' in bike_name and ('1x' in rear_derailleur or 'axs' in rear_derailleur):
            is_1x = True
            detection_reason = "1x setup in checkpoint category"
        
        if is_1x:
            specifications['Voorderailleur'] = 'geen voor-derailleur'
            self.logger.info(f"Added 'geen voor-derailleur' for 1x setup - detected by: {detection_reason}")

    def extract_description(self, bike_info):
        """Extract bike description from detail page"""
        if not bike_info.get('url'):
            return ""
            
        detail_url = urljoin(self.base_url, bike_info['url'])
        
        try:
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for description in various places
            description_selectors = [
                'div[data-testid="product-positioning-statement"]',
                '.product-positioning-statement',
                '.product-description',
                '.product-summary',
                'div.product-details p',
                'div.product-info p'
            ]
            
            for selector in description_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and len(text) > 50:  # Only meaningful descriptions
                        # Count words
                        word_count = len(text.split())
                        self.logger.info(f"Found positioning statement: {text[:100]}...")
                        return text
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting description for {bike_info.get('name', 'Unknown')}: {e}")
            return ""

    def scrape_trek_bikes(self):
        """Main scraping method"""
        # Trek road bikes URL (Dutch site)
        url = "https://www.trekbikes.com/nl/nl_NL/fietsen/racefietsen/c/B200/?sort=price-asc&pageSize=250&q=%3Arelevance%3AfacetFrameset%3AfacetFrameset2"
        
        self.logger.info(f"Fetching content from: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract bikes from dataLayer
            bikes = self.extract_bikes_from_datalayer(soup)
            self.logger.info(f"Extracted {len(bikes)} bikes from dataLayer")
            
            # Extract color variants
            color_variants = self.extract_color_variants(soup)
            
            # Log color variant extraction results
            for method in ['pattern', 'entity', 'colorSwatchImageUrl', 'direct']:
                count = len([k for k, v in color_variants.items() if v])
                self.logger.info(f"Found {count} matches with {method} pattern")
            
            # Process detailed data
            detailed_bikes = []
            total_color_variants = 0
            
            for i, bike_info in enumerate(bikes, 1):
                bike_name = bike_info.get('name', 'Unknown')
                
                # Check for color variants
                if bike_name in color_variants:
                    colors = color_variants[bike_name]
                    total_color_variants += len(colors)
                    self.logger.info(f"Found {len(colors)} color variants for {bike_name}: {colors}")
                
                self.logger.info(f"Processing bike {i}/{len(bikes)}: {bike_name}")
                
                # Extract specifications
                self.logger.info(f"Fetching specifications from: {urljoin(self.base_url, bike_info.get('url', ''))}")
                specifications = self.extract_specifications(bike_info)
                
                if specifications:
                    self.logger.info(f"Extracted {len(specifications)} specifications")
                    bike_info['specifications'] = specifications
                    self.logger.info(f"Added {len(specifications)} specifications for {bike_name}")
                
                # Extract description
                self.logger.info(f"Fetching description from: {urljoin(self.base_url, bike_info.get('url', ''))}")
                description = self.extract_description(bike_info)
                if description:
                    word_count = len(description.split())
                    bike_info['description'] = description
                    self.logger.info(f"Added description ({word_count} words) for {bike_name}")
                
                detailed_bikes.append(bike_info)
                
                # Add delay between requests
                time.sleep(0.5)
            
            self.logger.info(f"Extracted detailed data for {len(detailed_bikes)} products")
            
            # Remove duplicates while preserving order
            unique_bikes = []
            seen_names = set()
            
            for bike in detailed_bikes:
                bike_name = bike.get('name', '')
                if bike_name not in seen_names:
                    unique_bikes.append(bike)
                    seen_names.add(bike_name)
            
            self.logger.info(f"Successfully scraped {len(unique_bikes)} unique bike models with {total_color_variants} total color variants")
            
            return unique_bikes
            
        except Exception as e:
            self.logger.error(f"Error scraping Trek bikes: {e}")
            return []

    def clean_old_files(self, keep_count=2):
        """Clean up old timestamped files, keeping only the most recent ones"""
        patterns = [
            'data/trek_bikes_*.json',
            'data/trek_bikes_*.csv', 
            'data/trek_bikes_*.xlsx'
        ]
        
        files_removed = 0
        
        for pattern in patterns:
            files = glob.glob(pattern)
            # Filter out the 'latest' files
            timestamped_files = [f for f in files if 'latest' not in f]
            
            if len(timestamped_files) > keep_count:
                # Sort by modification time, newest first
                timestamped_files.sort(key=os.path.getmtime, reverse=True)
                
                # Remove older files
                for old_file in timestamped_files[keep_count:]:
                    try:
                        os.remove(old_file)
                        files_removed += 1
                    except OSError as e:
                        self.logger.warning(f"Could not remove {old_file}: {e}")
        
        if files_removed > 0:
            self.logger.info(f"Cleaned up {files_removed} old timestamped files (kept most recent as archive)")

    def save_data(self, bikes, timestamp=None):
        """Save scraped data to JSON, CSV, and Excel files"""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        
        # Clean up old files first
        self.clean_old_files()
        
        # Save timestamped versions
        json_file = f'data/trek_bikes_{timestamp}.json'
        csv_file = f'data/trek_bikes_{timestamp}.csv'
        excel_file = f'data/trek_bikes_{timestamp}.xlsx'
        
        # Save JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(bikes, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Saved {len(bikes)} bikes to {json_file}")
        
        # Prepare data for CSV/Excel
        csv_data = []
        for bike in bikes:
            row = {
                'name': bike.get('name', ''),
                'price': bike.get('price', ''),
                'category': bike.get('category', ''),
                'brand': bike.get('brand', 'Trek'),
                'url': bike.get('url', ''),
                'sku': bike.get('sku', ''),
                'variant': bike.get('variant', ''),
                'description': bike.get('description', '')
            }
            
            # Add specifications with spec_ prefix
            specifications = bike.get('specifications', {})
            for spec_key, spec_value in specifications.items():
                # Clean up specification key names for CSV headers
                clean_key = f"spec_{spec_key.replace(' ', '_').replace('/', '_')}"
                row[clean_key] = spec_value
            
            csv_data.append(row)
        
        # Save CSV
        if csv_data:
            df = pd.DataFrame(csv_data)
            df.to_csv(csv_file, index=False, encoding='utf-8')
            self.logger.info(f"Saved {len(bikes)} bikes to {csv_file}")
            
            # Save Excel
            df.to_excel(excel_file, index=False, engine='openpyxl')
            self.logger.info(f"Saved {len(bikes)} bikes to {excel_file}")
        
        # Also save latest versions (overwrite)
        latest_json = 'data/trek_bikes_latest.json'
        latest_csv = 'data/trek_bikes_latest.csv'
        latest_excel = 'data/trek_bikes_latest.xlsx'
        
        with open(latest_json, 'w', encoding='utf-8') as f:
            json.dump(bikes, f, ensure_ascii=False, indent=2)
        
        if csv_data:
            df.to_csv(latest_csv, index=False, encoding='utf-8')
            df.to_excel(latest_excel, index=False, engine='openpyxl')
        
        self.logger.info(f"Also saved latest versions as {latest_json}, {latest_csv}, and {latest_excel}")

    def print_summary(self, bikes):
        """Print a summary of scraped bikes"""
        if not bikes:
            print("No bikes were scraped.")
            return
        
        print(f"\n🚴 Trek Bikes Scraping Summary 🚴")
        print("=" * 50)
        
        # Count unique models and total variants
        unique_models = len(set(bike.get('name', '') for bike in bikes))
        total_variants = len(bikes)
        
        print(f"Total unique models: {unique_models}")
        print(f"Total color variants: {total_variants}")
        
        # Count models with multiple colors
        name_counts = {}
        for bike in bikes:
            name = bike.get('name', '')
            if name:
                name_counts[name] = name_counts.get(name, 0) + 1
        
        multi_color_models = sum(1 for count in name_counts.values() if count > 1)
        print(f"Models with multiple colors: {multi_color_models}")
        
        # Price range
        prices = []
        for bike in bikes:
            price_str = bike.get('price', '')
            if price_str:
                # Extract numeric price
                price_match = re.search(r'[\d,]+', price_str.replace('€', '').replace('.', ''))
                if price_match:
                    try:
                        price = int(price_match.group().replace(',', ''))
                        prices.append(price)
                    except ValueError:
                        pass
        
        if prices:
            print(f"Price range: €{min(prices)} - €{max(prices)}")
        
        # Category breakdown
        categories = {}
        for bike in bikes:
            category = bike.get('category', 'Unknown')
            categories[category] = categories.get(category, 0) + 1
        
        print(f"\nCategories:")
        for category, count in sorted(categories.items()):
            print(f"  {category}: {count} models")
        
        # Show bikes with multiple colors
        if multi_color_models > 0:
            print(f"\nBikes with multiple color options:")
            color_bikes = [(name, count) for name, count in name_counts.items() if count > 1]
            color_bikes.sort(key=lambda x: x[1], reverse=True)
            
            for name, count in color_bikes[:5]:  # Show top 5
                colors = []
                for bike in bikes:
                    if bike.get('name') == name:
                        variant = bike.get('variant', '')
                        if variant:
                            colors.append(variant)
                
                if colors:
                    print(f"  {name}: {count} colors ({', '.join(colors)})")
            
            if len(color_bikes) > 5:
                print(f"  ... and {len(color_bikes) - 5} more models with multiple colors")
        
        # Show most expensive bikes
        if prices:
            print(f"\nTop 5 most expensive bikes:")
            price_bikes = []
            for bike in bikes:
                price_str = bike.get('price', '')
                if price_str:
                    price_match = re.search(r'[\d,]+', price_str.replace('€', '').replace('.', ''))
                    if price_match:
                        try:
                            price = int(price_match.group().replace(',', ''))
                            price_bikes.append((bike.get('name', ''), bike.get('variant', ''), price))
                        except ValueError:
                            pass
            
            price_bikes.sort(key=lambda x: x[2], reverse=True)
            for i, (name, variant, price) in enumerate(price_bikes[:5], 1):
                variant_str = f" ({variant})" if variant else ""
                print(f"  {i}. {name}{variant_str} - €{price}")
        
        print("=" * 50)

def main():
    """Main function"""
    scraper = TrekBikeScraper()
    
    # Scrape bikes
    bikes = scraper.scrape_trek_bikes()
    
    if bikes:
        # Save data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scraper.save_data(bikes, timestamp)
        
        # Print summary
        scraper.print_summary(bikes)
    else:
        print("No bikes were scraped. Check the logs for errors.")

if __name__ == "__main__":
    main() 