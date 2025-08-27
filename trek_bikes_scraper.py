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
import shutil
from urllib.parse import urljoin, urlparse
import glob
from collections import defaultdict

# Import WordPress converter
try:
    from wordpress_csv_converter import convert_latest_to_wordpress
    WORDPRESS_CONVERTER_AVAILABLE = True
except ImportError:
    WORDPRESS_CONVERTER_AVAILABLE = False

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
        
        # Image download settings
        self.download_images = True  # Set to False to disable image downloading
        self.images_base_dir = "images"
        self.max_image_size_mb = 10  # Skip images larger than this
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.webp']

    def format_color_name(self, variant):
        """Format color variant name for better readability"""
        if not variant:
            return ''
        
        # Replace underscores with slashes and capitalize
        formatted = variant.replace('_', '/').replace('dark', ' Dark').replace('light', ' Light')
        
        # Capitalize each word
        words = formatted.split('/')
        formatted_words = []
        for word in words:
            word = word.strip()
            if word:
                # Handle special cases
                if word.lower() == 'reddark':
                    formatted_words.append('Red Dark')
                elif word.lower() == 'bluedark':
                    formatted_words.append('Blue Dark')
                elif word.lower() == 'greydark':
                    formatted_words.append('Grey Dark')
                elif word.lower() == 'greendark':
                    formatted_words.append('Green Dark')
                elif word.lower() == 'tealdark':
                    formatted_words.append('Teal Dark')
                elif word.lower() == 'bluelight':
                    formatted_words.append('Blue Light')
                elif word.lower() == 'greenlight':
                    formatted_words.append('Green Light')
                elif word.lower() == 'greylight':
                    formatted_words.append('Grey Light')
                else:
                    formatted_words.append(word.capitalize())
        
        return '/'.join(formatted_words)

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
                            'url': f"https://www.trekbikes.com/nl/nl_NL/p/{impression.get('id', '')}/",
                            'sku': impression.get('id', ''),
                            'variant': impression.get('variant', ''),
                            'color': self.format_color_name(impression.get('variant', ''))
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
                                        'url': f"https://www.trekbikes.com/nl/nl_NL/p/{item.get('item_id', '')}/",
                                        'sku': item.get('item_id', ''),
                                        'variant': item.get('item_variant', ''),
                                        'color': self.format_color_name(item.get('item_variant', ''))
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
            
            # Clean up Frame specification to show only material
            if 'Frame' in specifications:
                specifications['Frame'] = self.extract_frame_material(specifications['Frame'])
            elif 'Frame plus vork' in specifications:
                # Some bikes (like Madone models) have frame specs under "Frame plus vork"
                specifications['Frame'] = self.extract_frame_material(specifications['Frame plus vork'])
                self.logger.info(f"Used 'Frame plus vork' for frame material: {specifications['Frame']}")
            
            # Clean up Gewichtslimiet specification to show only weight limit
            if 'Gewichtslimiet' in specifications:
                specifications['Gewichtslimiet'] = self.extract_weight_limit(specifications['Gewichtslimiet'])
            
            # Clean up Gewicht specification to remove lbs indications
            if 'Gewicht' in specifications:
                specifications['Gewicht'] = self.clean_weight_specification(specifications['Gewicht'])
                # Standardize frame size notation (add cm to numeric sizes)
                specifications['Gewicht'] = self.standardize_frame_size_in_weight(specifications['Gewicht'])
            
            # Clean up Shifter specification to remove frame size information
            if 'Shifter' in specifications:
                # Extract shifter speed before cleaning
                shifter_speed = self.extract_shifter_speed(specifications['Shifter'])
                if shifter_speed:
                    specifications['Shifter_speed'] = shifter_speed
                
                # Clean frame size information
                specifications['Shifter'] = self.clean_shifter_specification(specifications['Shifter'])
                
                # Remove speed information from shifter spec
                specifications['Shifter'] = self.clean_shifter_speed_from_spec(specifications['Shifter'])
            
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

    def extract_weight_limit(self, weight_limit_spec):
        """Extract only the weight limit value from full weight limit specification"""
        if not weight_limit_spec:
            return weight_limit_spec
            
        # Convert to string and clean up
        weight_limit_spec = str(weight_limit_spec).strip()
        
        # Look for weight patterns in the text
        import re
        
        # Pattern to match weight limits like "125 kg", "150 kg", etc.
        weight_patterns = [
            r'(\d+(?:[.,]\d+)?\s*kg)',
            r'(\d+(?:[.,]\d+)?\s*lbs?)',
        ]
        
        for pattern in weight_patterns:
            match = re.search(pattern, weight_limit_spec, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # If no pattern found, return original
        return weight_limit_spec

    def clean_weight_specification(self, weight_spec):
        """Remove lbs indications from weight specification, keep only kg"""
        if not weight_spec:
            return weight_spec
            
        # Convert to string and clean up
        weight_spec = str(weight_spec).strip()
        
        # Look for patterns like "8.43 kg / 18.59 lbs" and keep only the kg part
        import re
        
        # Pattern to match kg value followed by optional lbs part
        # This will match things like "8.43 kg / 18.59 lbs" and extract just "8.43 kg"
        kg_pattern = r'(\d+(?:[.,]\d+)?\s*kg)(?:\s*/\s*\d+(?:[.,]\d+)?\s*lbs)?'
        
        # Find all kg values and remove any lbs parts
        matches = re.findall(kg_pattern, weight_spec, re.IGNORECASE)
        
        if matches:
            # Replace the original kg/lbs pattern with just the kg part
            cleaned_spec = weight_spec
            for match in matches:
                # Find the full pattern (kg + lbs) and replace with just kg
                full_pattern = r'\d+(?:[.,]\d+)?\s*kg\s*/\s*\d+(?:[.,]\d+)?\s*lbs'
                cleaned_spec = re.sub(full_pattern, match, cleaned_spec, flags=re.IGNORECASE)
            
            return cleaned_spec
        
        # If no kg/lbs pattern found, return original
        return weight_spec

    def standardize_frame_size_in_weight(self, weight_spec):
        """Standardize frame size notation in weight specification by adding cm to numeric sizes"""
        if not weight_spec:
            return weight_spec
            
        # Convert to string and clean up
        weight_spec = str(weight_spec).strip()
        
        import re
        
        # Pattern to match numeric frame sizes without cm (like "56 -" but not "56 cm -")
        # This will match patterns like "56 -" or "58 -" but not "56 cm -" or "ML -" or "M -"
        numeric_size_pattern = r'(\d+)\s*-\s*(\d+(?:[.,]\d+)?\s*kg)'
        
        # Check if there's already a cm in the string
        if 'cm' not in weight_spec:
            # Replace numeric sizes with cm added
            def add_cm(match):
                size = match.group(1)
                weight_part = match.group(2)
                return f"{size} cm - {weight_part}"
            
            weight_spec = re.sub(numeric_size_pattern, add_cm, weight_spec)
        
        return weight_spec

    def clean_shifter_specification(self, shifter_spec):
        """Remove frame size information from shifter specification"""
        if not shifter_spec:
            return shifter_spec
            
        # Convert to string and clean up
        shifter_spec = str(shifter_spec).strip()
        
        import re
        
        # Pattern to match frame size information at the beginning
        # This will remove patterns like:
        # - "Maat: 47, 50, 52, 54, 56, 58, 60, 62 "
        # - "Maat: XS, S, M, ML, L, XL "
        size_patterns = [
            r'^Maat:\s*(?:\d+(?:\s*,\s*\d+)*)\s+',  # Numeric sizes
            r'^Maat:\s*(?:[A-Z]+(?:\s*,\s*[A-Z]+)*)\s+',  # Letter sizes (XS, S, M, ML, L, XL)
        ]
        
        # Remove any size pattern from the beginning
        for pattern in size_patterns:
            cleaned_spec = re.sub(pattern, '', shifter_spec, flags=re.IGNORECASE)
            if cleaned_spec != shifter_spec:
                # Pattern matched, use the cleaned version
                shifter_spec = cleaned_spec
                break
        
        return shifter_spec.strip()

    def extract_shifter_speed(self, shifter_spec):
        """Extract speed information from shifter specification"""
        if not shifter_spec:
            return None
            
        # Convert to string and clean up
        shifter_spec = str(shifter_spec).strip()
        
        import re
        
        # Patterns to match speed information
        speed_patterns = [
            r'(\d+)\s*speed',           # "8 speed", "10 Speed"
            r'(\d+)-speed',             # "9-speed", "11-speed"
            r'(\d+)\s*versnellingen',   # "10 versnellingen"
        ]
        
        for pattern in speed_patterns:
            match = re.search(pattern, shifter_spec, re.IGNORECASE)
            if match:
                return f"{match.group(1)}-speed"
        
        # For high-end bikes without explicit speed info, try to infer from components
        # SRAM RED AXS E1 is typically 12-speed
        if 'SRAM RED AXS E1' in shifter_spec:
            return "12-speed"
        
        # SRAM AXS systems are typically 12-speed for road bikes
        if 'SRAM AXS' in shifter_spec and 'draadloze' in shifter_spec:
            return "12-speed"
        
        # Shimano Dura-Ace Di2 systems are typically 11 or 12-speed
        if 'Shimano Dura-Ace' in shifter_spec and 'Di2' in shifter_spec:
            return "11-speed"  # Conservative estimate for older Di2 systems
        
        return None

    def clean_shifter_speed_from_spec(self, shifter_spec):
        """Remove speed information from shifter specification"""
        if not shifter_spec:
            return shifter_spec
            
        # Convert to string and clean up
        shifter_spec = str(shifter_spec).strip()
        
        import re
        
        # Patterns to remove speed information
        speed_patterns = [
            r',?\s*\d+\s*speed\s*,?',           # ", 8 speed,", "10 Speed"
            r',?\s*\d+-speed\s*,?',             # ", 9-speed,", "11-speed"
            r',?\s*\d+\s*versnellingen\s*,?',   # ", 10 versnellingen,"
        ]
        
        for pattern in speed_patterns:
            shifter_spec = re.sub(pattern, '', shifter_spec, flags=re.IGNORECASE)
        
        # Clean up any double commas or spaces
        shifter_spec = re.sub(r',\s*,', ',', shifter_spec)
        shifter_spec = re.sub(r'\s+', ' ', shifter_spec)
        shifter_spec = shifter_spec.strip(' ,')
        
        return shifter_spec

    def extract_frame_material(self, frame_spec):
        """Extract only the core frame material from full frame specification"""
        if not frame_spec:
            return frame_spec
            
        # Convert to string and clean up
        frame_spec = str(frame_spec).strip()
        
        # Common frame material patterns
        patterns = [
            # OCLV Carbon patterns
            r'(\d+\s+[Ss]eries\s+OCLV\s+Carbon)',
            r'(OCLV\s+Carbon\s+\d+)',
            r'(OCLV\s+Carbon)',
            # Alpha Aluminium patterns  
            r'(Ultralicht\s+\d+\s+[Ss]eries\s+Alpha\s+Aluminium)',
            r'(\d+\s+[Ss]eries\s+Alpha\s+Aluminium)',
            r'(Alpha\s+Aluminium\s+\d+)',
            r'(Alpha\s+Aluminium)',
            # Other materials
            r'(Carbon\s+fiber)',
            r'(Steel)',
            r'(Titanium)',
            r'(Chromoly)',
        ]
        
        # Try each pattern
        for pattern in patterns:
            import re
            match = re.search(pattern, frame_spec, re.IGNORECASE)
            if match:
                material = match.group(1)
                # Capitalize properly
                material = ' '.join(word.capitalize() for word in material.split())
                self.logger.info(f"Extracted frame material: {material} from: {frame_spec[:50]}...")
                return material
        
        # If no pattern matches, try to extract the first meaningful part
        # Split by comma and take the first part
        first_part = frame_spec.split(',')[0].strip()
        if first_part and len(first_part) < 100:
            # Clean up common prefixes/suffixes
            first_part = re.sub(r'^(Frame[:\s]*)', '', first_part, flags=re.IGNORECASE)
            first_part = first_part.strip()
            if first_part:
                self.logger.info(f"Using first part as frame material: {first_part}")
                return first_part
        
        # Fallback: return original if nothing else works
        self.logger.warning(f"Could not extract frame material from: {frame_spec[:50]}...")
        return frame_spec

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
        crankstel = specifications.get('Crankstel', '').lower()
        cassette = specifications.get('Cassette', '').lower()
        rear_derailleur = specifications.get('Achterderailleur', '').lower()
        bike_name = bike_info.get('name', '').lower()
        
        is_1x = False
        detection_reason = ""
        
        # First, check if this is clearly a 2x system - if so, don't classify as 1x
        if self.is_2x_system(crankstel):
            # This is a 2x system, skip 1x classification
            pass
        # Check for explicit 1x indicators in chainring
        elif 'x' in chainring and not '2x' in chainring:
            is_1x = True
            detection_reason = "1x-only chainring specification"
        
        # Check for single chainring patterns in crankstel
        elif self.is_single_chainring_crankstel(crankstel):
            is_1x = True
            detection_reason = "single chainring in crankstel"
        
        # Check for wide range cassettes (typical for 1x systems)
        elif self.is_wide_range_cassette(cassette):
            cassette_range = re.search(r'(\d+)-(\d+)', cassette)
            if cassette_range:
                min_teeth = int(cassette_range.group(1))
                max_teeth = int(cassette_range.group(2))
                is_1x = True
                detection_reason = f"wide cassette range ({max_teeth - min_teeth} teeth)"
        
        # Check for 1x-specific rear derailleurs
        elif self.is_1x_rear_derailleur(rear_derailleur):
            is_1x = True
            detection_reason = "1x-specific rear derailleur"
        
        # Check for bike categories that are typically 1x (only if crankstel doesn't contradict)
        elif self.is_1x_bike_category(bike_name):
            is_1x = True
            detection_reason = "1x setup in bike category"
        
        # If we detected a 1x system, set the front derailleur
        if is_1x:
            specifications['Voorderailleur'] = '1x, geen voorderailleur'
            self.logger.info(f"Added '1x, geen voorderailleur' for 1x setup - detected by: {detection_reason}")
        
        # If Voorderailleur is empty and we haven't detected 1x, check if it should be empty
        elif not specifications.get('Voorderailleur', '').strip():
            # For bikes without front derailleur info, check if it might be a 1x that we missed
            if self.likely_1x_system(crankstel, cassette, rear_derailleur, bike_name):
                specifications['Voorderailleur'] = '1x, geen voorderailleur'
                self.logger.info(f"Added '1x, geen voorderailleur' for likely 1x system based on component analysis")
            # Check if this is a 2x system that should have a front derailleur
            elif self.is_2x_system(crankstel):
                specifications['Voorderailleur'] = '2x systeem, voorderailleur aanwezig'
                self.logger.info(f"Added '2x systeem, voorderailleur aanwezig' for 2x system based on crankstel analysis")
            else:
                # Log that we found an empty front derailleur that doesn't seem to be 1x or 2x
                self.logger.warning(f"Empty Voorderailleur for {bike_info.get('name', 'Unknown')} - may need manual review")
    
    def is_single_chainring_crankstel(self, crankstel):
        """Check if crankstel indicates a single chainring setup"""
        if not crankstel:
            return False
        
        # First, check for double chainring patterns (2x systems)
        double_chainring_patterns = [
            r'\d+/\d+',   # "50/34" pattern
            r'\d+x\d+',   # "46x30" pattern (Trek uses this format!)
        ]
        
        for pattern in double_chainring_patterns:
            if re.search(pattern, crankstel, re.IGNORECASE):
                return False  # This is a 2x system, not 1x
        
        # Look for single chainring patterns
        single_chainring_patterns = [
            r'\b40t\b.*ring',           # "40T ring"
            r'\b42t\b.*ring',           # "42T ring"
            r'\b40t\b.*kettingblad',    # "40T kettingblad"
            r'\b42t\b.*kettingblad',    # "42T kettingblad"
            r'narrow-wide.*kettingblad', # "narrow-wide kettingblad"
            r'apex 1',                  # "SRAM Apex 1"
            r'force.*1',                # "SRAM Force 1"
            r'single.*chainring',       # "single chainring"
        ]
        
        for pattern in single_chainring_patterns:
            if re.search(pattern, crankstel, re.IGNORECASE):
                return True
        
        # Check for single number followed by T (like "40T")
        single_chainring = re.search(r'\b(\d+)t\b', crankstel, re.IGNORECASE)
        if single_chainring:
            teeth = int(single_chainring.group(1))
            # Single chainrings are typically 38-46T for road/gravel
            if 38 <= teeth <= 46:
                return True
        
        return False
    
    def is_wide_range_cassette(self, cassette):
        """Check if cassette indicates a wide range typical of 1x systems"""
        if not cassette:
            return False
        
        # Wide range cassette patterns for 1x systems
        wide_range_patterns = [
            r'10-50', r'10-52', r'11-50', r'11-52',  # Very wide ranges
            r'10-44', r'10-46', r'11-44', r'11-46',  # Wide ranges
            r'10-48', r'11-48',                      # Common 1x ranges
            r'10-42', r'11-42',                      # Moderate 1x ranges
        ]
        
        for pattern in wide_range_patterns:
            if re.search(pattern, cassette, re.IGNORECASE):
                return True
        
        # Check for numerical range
        cassette_range = re.search(r'(\d+)-(\d+)', cassette)
        if cassette_range:
            min_teeth = int(cassette_range.group(1))
            max_teeth = int(cassette_range.group(2))
            range_size = max_teeth - min_teeth
            
            # Wide range indicates 1x (typically >30 teeth range)
            if range_size >= 30:
                return True
        
        return False
    
    def is_1x_rear_derailleur(self, rear_derailleur):
        """Check if rear derailleur is 1x-specific"""
        if not rear_derailleur:
            return False
        
        # 1x-specific rear derailleur patterns
        onex_patterns = [
            r'apex 1',              # "SRAM Apex 1"
            r'apex.*xplr',          # "SRAM Apex XPLR"
            r'force.*xplr',         # "SRAM Force XPLR"
            r'red.*xplr',           # "SRAM RED XPLR"
            r'rival.*xplr',         # "SRAM Rival XPLR"
            r'grx.*1x',             # "Shimano GRX 1x"
            r'cues.*gs',            # "Shimano CUES GS" (often 1x)
        ]
        
        for pattern in onex_patterns:
            if re.search(pattern, rear_derailleur, re.IGNORECASE):
                return True
        
        return False
    
    def is_1x_bike_category(self, bike_name):
        """Check if bike category typically uses 1x systems"""
        # Gravel and some fitness bikes often use 1x
        onex_categories = [
            'checkpoint.*alr.*[345]',   # Checkpoint ALR 3, 4, 5 often 1x
            'fx.*sport',                # FX Sport bikes often 1x
            'checkmate',                # Checkmate is typically 1x
            'boone.*5',                 # Boone 5 often 1x
        ]
        
        for pattern in onex_categories:
            if re.search(pattern, bike_name, re.IGNORECASE):
                return True
        
        return False
    
    def likely_1x_system(self, crankstel, cassette, rear_derailleur, bike_name):
        """Determine if a bike is likely a 1x system based on multiple indicators"""
        score = 0
        
        # Check individual components
        if self.is_single_chainring_crankstel(crankstel):
            score += 3
        
        if self.is_wide_range_cassette(cassette):
            score += 2
        
        if self.is_1x_rear_derailleur(rear_derailleur):
            score += 2
        
        if self.is_1x_bike_category(bike_name):
            score += 1
        
        # Check for specific component combinations
        if 'cues' in rear_derailleur and ('11-48' in cassette or '11-50' in cassette):
            score += 2
        
        if 'apex' in rear_derailleur and ('11-42' in cassette or '11-44' in cassette):
            score += 2
        
        # Score >= 3 indicates likely 1x system
        return score >= 3
    
    def is_2x_system(self, crankstel):
        """Check if crankstel indicates a 2x (double chainring) setup"""
        if not crankstel:
            return False
        
        # Look for double chainring patterns like "50/34", "52/36", "48/35", "46x30"
        double_chainring_patterns = [
            r'\d+/\d+',   # "50/34" pattern
            r'\d+x\d+',   # "46x30" pattern (Trek uses this format!)
        ]
        
        for pattern in double_chainring_patterns:
            if re.search(pattern, crankstel):
                return True
        
        return False

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

    def extract_hero_carousel_images(self, bike_info):
        """Extract all hero carousel images from bike detail page including color variants"""
        if not bike_info.get('url'):
            return []
            
        detail_url = urljoin(self.base_url, bike_info['url'])
        
        try:
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            hero_images = []
            html_content = str(soup)
            
            # Decode HTML entities to handle encoded quotes properly
            import html as html_module
            decoded_content = html_module.unescape(html_content)
            
            # Comprehensive patterns to find all carousel images
            image_patterns = [
                # Enhanced structured data patterns
                r'"heroCarousel"\s*:\s*\[([^\]]+)\]',
                r'"productImages"\s*:\s*\[([^\]]+)\]',
                r'"imageGallery"\s*:\s*\[([^\]]+)\]',
                r'"gallery"\s*:\s*\[([^\]]+)\]',
                r'"images"\s*:\s*\[([^\]]+)\]',
                r'"slides"\s*:\s*\[([^\]]+)\]',
                r'"carouselSlides"\s*:\s*\[([^\]]+)\]',
                
                # Color variant specific patterns
                r'"colorSwatchImageUrl"\s*:\s*\[([^\]]+)\]',
                r'"variantImages"\s*:\s*\[([^\]]+)\]',
                r'"colorVariants"\s*:\s*\[([^\]]+)\]',
                
                # Individual image patterns
                r'"heroImage"\s*:\s*"([^"]*media\.trekbikes\.com[^"]*)"',
                r'"primaryImage"\s*:\s*"([^"]*media\.trekbikes\.com[^"]*)"',
                r'"firstVariantImage"\s*:\s*"([^"]*media\.trekbikes\.com[^"]*)"',
                r'"thumbnailImage"\s*:\s*"([^"]*media\.trekbikes\.com[^"]*)"',
                
                # URL patterns with various prefixes
                r'"[a-zA-Z_]*[Uu]rl"\s*:\s*"([^"]*media\.trekbikes\.com[^"]*)"',
                r'"[a-zA-Z_]*[Ii]mage[a-zA-Z_]*"\s*:\s*"([^"]*media\.trekbikes\.com[^"]*)"',
                
                # Enhanced alternative image arrays
                r'"primaryImages"\s*:\s*\[([^\]]+)\]',
                r'"galleryImages"\s*:\s*\[([^\]]+)\]',
                r'"productGallery"\s*:\s*\[([^\]]+)\]',
                r'"heroImages"\s*:\s*\[([^\]]+)\]',
            ]
            
            # Process structured data patterns (arrays) - use decoded content
            for pattern in image_patterns[:13]:  # First 13 are array patterns
                matches = re.findall(pattern, decoded_content, re.DOTALL)
                for match in matches:
                    # Extract all image URLs from the array content
                    image_urls = re.findall(r'"([^"]*media\.trekbikes\.com[^"]*)"', match)
                    for url in image_urls:
                        # Clean up malformed URLs that have color prefixes
                        if '=' in url and '//' in url:
                            url = url.split('=', 1)[-1]
                            
                        if url.startswith('//'):
                            url = 'https:' + url
                        elif not url.startswith('http'):
                            url = 'https://' + url
                            
                        # Skip malformed URLs
                        if not url.startswith('https://media.trekbikes.com'):
                            continue
                            
                        hero_images.append(url)
            
            # Process individual image patterns - use decoded content
            for pattern in image_patterns[13:16]:  # Individual image patterns
                matches = re.findall(pattern, decoded_content)
                for match in matches:
                    # Clean up malformed URLs that have color prefixes
                    if '=' in match and '//' in match:
                        match = match.split('=', 1)[-1]
                        
                    if match.startswith('//'):
                        match = 'https:' + match
                    elif not match.startswith('http'):
                        match = 'https://' + match
                        
                    # Skip malformed URLs
                    if not match.startswith('https://media.trekbikes.com'):
                        continue
                        
                    hero_images.append(match)
            
            # Process URL and image patterns with various prefixes - use decoded content
            for pattern in image_patterns[16:18]:  # URL patterns
                matches = re.findall(pattern, decoded_content)
                for match in matches:
                    if '=' in match and '//' in match:
                        match = match.split('=', 1)[-1]
                        
                    if match.startswith('//'):
                        match = 'https:' + match
                    elif not match.startswith('http'):
                        match = 'https://' + match
                        
                    if not match.startswith('https://media.trekbikes.com'):
                        continue
                        
                    hero_images.append(match)
            
            # Process alternative image arrays - use decoded content
            for pattern in image_patterns[18:]:  # Alternative image arrays
                matches = re.findall(pattern, decoded_content, re.DOTALL)
                for match in matches:
                    image_urls = re.findall(r'"([^"]*media\.trekbikes\.com[^"]*)"', match)
                    for url in image_urls:
                        # Clean up malformed URLs that have color prefixes
                        if '=' in url and '//' in url:
                            url = url.split('=', 1)[-1]
                            
                        if url.startswith('//'):
                            url = 'https:' + url
                        elif not url.startswith('http'):
                            url = 'https://' + url
                            
                        if not url.startswith('https://media.trekbikes.com'):
                            continue
                            
                        hero_images.append(url)
            
            # Also search for any high-quality Trek images in the page - use decoded content
            all_trek_images = re.findall(r'([^"]*media\.trekbikes\.com[^"]*)', decoded_content)
            for img_url in all_trek_images:
                # Clean up malformed URLs that have color prefixes
                if '=' in img_url and '//' in img_url:
                    # Extract the actual URL after the = sign
                    img_url = img_url.split('=', 1)[-1]
                
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif not img_url.startswith('http'):
                    img_url = 'https://' + img_url
                    
                # Skip malformed URLs
                if not img_url.startswith('https://media.trekbikes.com'):
                    continue
                    
                hero_images.append(img_url)
            
            # Filter for high-quality images and remove unwanted types
            quality_images = []
            for img_url in hero_images:
                # Must be a Trek media URL
                if 'media.trekbikes.com' not in img_url:
                    continue
                    
                # Skip tiny thumbnails and low-quality images
                if any(skip in img_url.lower() for skip in ['thumb', 'icon', 'logo', 'badge', 'w_50', 'w_100', 'w_150', 'h_50', 'h_100']):
                    continue
                
                # Skip default placeholder images
                if any(skip in img_url for skip in ['default-no-image', 'CyclingTips']):
                    continue
                
                # Prefer high-quality images
                is_high_quality = any(quality in img_url for quality in [
                    'w_1360', 'w_1200', 'w_690', 'w_800', 'w_1000',
                    'Primary', 'Hero', 'Detail', 'Gallery', 'Portrait',
                    'h_1020', 'h_800', 'h_600'
                ])
                
                # Accept medium quality if we don't have many images yet
                is_medium_quality = any(medium in img_url for medium in [
                    'w_400', 'w_500', 'w_600', 'h_300', 'h_400', 'h_518'
                ])
                
                if is_high_quality or (is_medium_quality and len(quality_images) < 10):
                    quality_images.append(img_url)
            
            # Remove duplicates while preserving order
            unique_images = []
            seen_urls = set()
            seen_paths = set()  # Track image paths to avoid same image with different transformations
            
            for img_url in quality_images:
                # Extract the base image path to avoid duplicates with different sizes
                base_path = re.sub(r'/image/upload/[^/]+/', '/image/upload/', img_url)
                
                if img_url not in seen_urls and base_path not in seen_paths:
                    unique_images.append(img_url)
                    seen_urls.add(img_url)
                    seen_paths.add(base_path)
            
            if unique_images:
                self.logger.info(f"Found {len(unique_images)} hero carousel images for {bike_info.get('name', 'Unknown')}")
                for i, img_url in enumerate(unique_images, 1):
                    self.logger.debug(f"  Image {i}: {img_url}")
            else:
                self.logger.warning(f"No hero carousel images found for {bike_info.get('name', 'Unknown')}")
            
            return unique_images
            
        except Exception as e:
            self.logger.error(f"Error extracting hero carousel images for {bike_info.get('name', 'Unknown')}: {e}")
            return []


    def download_image(self, image_url, save_path):
        """Download a single image from URL to save_path"""
        try:
            # Check if file already exists
            if os.path.exists(save_path):
                self.logger.info(f"Image already exists, skipping: {os.path.basename(save_path)}")
                return True
            
            # Download the image
            response = self.session.get(image_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Check file size
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > self.max_image_size_mb:
                    self.logger.warning(f"Skipping large image ({size_mb:.1f}MB): {image_url}")
                    return False
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Save the image
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(save_path) / (1024 * 1024)
            self.logger.info(f"Downloaded image ({file_size:.1f}MB): {os.path.basename(save_path)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading image {image_url}: {e}")
            return False

    def get_image_filename_from_url(self, image_url):
        """Extract a clean filename from image URL"""
        # Parse the URL to get the path
        parsed_url = urlparse(image_url)
        path = parsed_url.path
        
        # Extract filename from path
        filename = os.path.basename(path)
        
        # If no filename or no extension, create one from the path
        if not filename or '.' not in filename:
            # Use the last part of the path before query parameters
            path_parts = [part for part in path.split('/') if part]
            if path_parts:
                filename = path_parts[-1]
                # Add .jpg extension if no extension present
                if '.' not in filename:
                    filename += '.jpg'
            else:
                filename = 'image.jpg'
        
        # Clean up filename - remove special characters
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        return filename

    def save_bike_images(self, bike_info, hero_images):
        """Save all hero carousel images for a bike with proper organization"""
        if not hero_images or not self.download_images:
            return []
        
        bike_name = bike_info.get('name', 'Unknown')
        brand = bike_info.get('brand', 'Trek')
        
        # Clean bike name for folder structure
        clean_bike_name = re.sub(r'[^\w\-_\s]', '', bike_name)
        clean_bike_name = re.sub(r'\s+', '_', clean_bike_name.strip())
        
        # Create brand folder path
        brand_folder = os.path.join(self.images_base_dir, brand)
        bike_folder = os.path.join(brand_folder, clean_bike_name)
        
        downloaded_images = []
        
        for i, image_url in enumerate(hero_images):
            try:
                # Get filename from URL
                original_filename = self.get_image_filename_from_url(image_url)
                
                # Create numbered filename to handle multiple images
                name_part, ext_part = os.path.splitext(original_filename)
                if len(hero_images) > 1:
                    numbered_filename = f"{name_part}_{i+1:02d}{ext_part}"
                else:
                    numbered_filename = original_filename
                
                # Full save path
                save_path = os.path.join(bike_folder, numbered_filename)
                
                # Download the image
                if self.download_image(image_url, save_path):
                    downloaded_images.append({
                        'url': image_url,
                        'local_path': save_path,
                        'filename': numbered_filename
                    })
                
            except Exception as e:
                self.logger.error(f"Error saving image {i+1} for {bike_name}: {e}")
        
        if downloaded_images:
            self.logger.info(f"Downloaded {len(downloaded_images)} images for {bike_name}")
        
        return downloaded_images

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
                
                # Extract and download hero carousel images
                self.logger.info(f"Fetching hero carousel images from: {urljoin(self.base_url, bike_info.get('url', ''))}")
                hero_images = self.extract_hero_carousel_images(bike_info)
                if hero_images:
                    # Download the images
                    downloaded_images = self.save_bike_images(bike_info, hero_images)
                    if downloaded_images:
                        bike_info['hero_images'] = downloaded_images
                        self.logger.info(f"Downloaded {len(downloaded_images)} hero carousel images for {bike_name}")
                
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

    def clean_old_files(self, keep_count=3):
        """Move old timestamped files to archive, keeping only the most recent ones in working directories"""
        patterns_and_archive_dirs = [
            ('data/Trek/trek_bikes_*.json', 'data/archive/Trek'),
            ('data/Trek/trek_bikes_*.csv', 'data/archive/Trek'), 
            ('data/Trek/trek_bikes_*.xlsx', 'data/archive/Trek'),
            ('data/wordpress_imports/trek_bikes_wordpress_*.csv', 'data/archive/wordpress_imports')
        ]
        
        files_archived = 0
        
        for pattern, archive_dir in patterns_and_archive_dirs:
            files = glob.glob(pattern)
            # All files in brand and wordpress folders are timestamped (no 'latest' files there)
            timestamped_files = files
            
            if len(timestamped_files) > keep_count:
                # Ensure archive directory exists
                os.makedirs(archive_dir, exist_ok=True)
                
                # Sort by modification time, newest first
                timestamped_files.sort(key=os.path.getmtime, reverse=True)
                
                # Move older files to archive
                for old_file in timestamped_files[keep_count:]:
                    try:
                        import shutil
                        filename = os.path.basename(old_file)
                        archive_path = os.path.join(archive_dir, filename)
                        
                        # If file already exists in archive, add timestamp to avoid conflicts
                        if os.path.exists(archive_path):
                            name, ext = os.path.splitext(filename)
                            archive_path = os.path.join(archive_dir, f"{name}_archived_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
                        
                        shutil.move(old_file, archive_path)
                        files_archived += 1
                        self.logger.info(f"Archived old file: {old_file} → {archive_path}")
                    except OSError as e:
                        self.logger.warning(f"Could not archive {old_file}: {e}")
        
        if files_archived > 0:
            self.logger.info(f"Archived {files_archived} old timestamped files (kept {keep_count} most recent in working directories)")

    def save_data(self, bikes, timestamp=None):
        """Save scraped data to JSON, CSV, and Excel files"""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure directories exist
        brand_dir = 'data/Trek'
        os.makedirs(brand_dir, exist_ok=True)
        os.makedirs('data', exist_ok=True)  # Keep data root for 'latest' files
        
        # Clean up old files first
        self.clean_old_files()
        
        # Save timestamped versions in brand folder
        json_file = f'{brand_dir}/trek_bikes_{timestamp}.json'
        csv_file = f'{brand_dir}/trek_bikes_{timestamp}.csv'
        excel_file = f'{brand_dir}/trek_bikes_{timestamp}.xlsx'
        
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
                'color': bike.get('color', ''),
                'description': bike.get('description', '')
            }
            
            # Add specifications with spec_ prefix
            specifications = bike.get('specifications', {})
            for spec_key, spec_value in specifications.items():
                # Clean up specification key names for CSV headers
                clean_key = f"spec_{spec_key.replace(' ', '_').replace('/', '_')}"
                row[clean_key] = spec_value
            
            # Add hero images
            hero_images = bike.get('hero_images', [])
            if hero_images:
                for i, img_info in enumerate(hero_images):
                    if isinstance(img_info, dict):
                        row[f'hero_image_{i+1}_url'] = img_info.get('url', '')
                        row[f'hero_image_{i+1}_path'] = img_info.get('local_path', '')
                        row[f'hero_image_{i+1}_filename'] = img_info.get('filename', '')
                    else:
                        # Handle case where it's just a URL string
                        row[f'hero_image_{i+1}_url'] = str(img_info)
            
            csv_data.append(row)
        
        # Save CSV
        if csv_data:
            df = pd.DataFrame(csv_data)
            df.to_csv(csv_file, index=False, encoding='utf-8', quoting=1)  # QUOTE_ALL for proper CSV format
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
            df.to_csv(latest_csv, index=False, encoding='utf-8', quoting=1)  # QUOTE_ALL for proper CSV format
            df.to_excel(latest_excel, index=False, engine='openpyxl')
        
        self.logger.info(f"Also saved latest versions as {latest_json}, {latest_csv}, and {latest_excel}")
        
        # Automatically generate WordPress-ready CSV
        if WORDPRESS_CONVERTER_AVAILABLE and csv_data:
            try:
                self.logger.info("Generating WordPress-ready CSV...")
                wp_file = convert_latest_to_wordpress(verbose=False)
                if wp_file:
                    self.logger.info(f"WordPress CSV generated: {wp_file}")
                else:
                    self.logger.warning("WordPress CSV generation failed")
            except Exception as e:
                self.logger.error(f"Error generating WordPress CSV: {e}")
        elif not WORDPRESS_CONVERTER_AVAILABLE:
            self.logger.warning("WordPress converter not available (wordpress_csv_converter.py not found)")

    def analyze_color_variants(self, bikes):
        """Analyze and group bikes by model to show color variants"""
        model_colors = {}
        
        for bike in bikes:
            name = bike.get('name', '')
            color = bike.get('color', '')
            variant = bike.get('variant', '')
            
            if name:
                if name not in model_colors:
                    model_colors[name] = []
                
                color_info = {
                    'color': color,
                    'variant': variant,
                    'price': bike.get('price', ''),
                    'url': bike.get('url', '')
                }
                model_colors[name].append(color_info)
        
        return model_colors

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
        
        # Show color variants analysis
        model_colors = self.analyze_color_variants(bikes)
        models_with_multiple_colors = {name: colors for name, colors in model_colors.items() if len(colors) > 1}
        
        if models_with_multiple_colors:
            print(f"\n🎨 Color Variants Analysis:")
            print(f"Models with multiple colors: {len(models_with_multiple_colors)}")
            
            for name, colors in list(models_with_multiple_colors.items())[:5]:  # Show top 5
                color_names = [c['color'] for c in colors if c['color']]
                print(f"  {name}: {len(colors)} colors")
                for color_info in colors:
                    if color_info['color']:
                        print(f"    - {color_info['color']} ({color_info['variant']})")
            
            if len(models_with_multiple_colors) > 5:
                print(f"  ... and {len(models_with_multiple_colors) - 5} more models with multiple colors")
        
        # Show all unique colors
        all_colors = set()
        for bike in bikes:
            color = bike.get('color', '')
            if color:
                all_colors.add(color)
        
        print(f"\n🎨 All Available Colors ({len(all_colors)}):")
        for color in sorted(all_colors):
            count = sum(1 for bike in bikes if bike.get('color') == color)
            print(f"  {color}: {count} bikes")
        
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

    def print_image_summary(self, bikes):
        """Print summary of image download statistics"""
        print("\n" + "=" * 50)
        print("IMAGE DOWNLOAD SUMMARY")
        print("=" * 50)
        
        total_bikes = len(bikes)
        bikes_with_images = 0
        total_images_downloaded = 0
        total_image_urls_found = 0
        
        brand_stats = defaultdict(lambda: {'bikes': 0, 'images': 0})
        
        for bike in bikes:
            bike_name = bike.get('name', 'Unknown')
            brand = bike.get('brand', 'Trek')
            hero_images = bike.get('hero_images', [])
            
            if hero_images:
                bikes_with_images += 1
                total_images_downloaded += len(hero_images)
                brand_stats[brand]['bikes'] += 1
                brand_stats[brand]['images'] += len(hero_images)
        
        print(f"Total bikes processed: {total_bikes}")
        print(f"Bikes with images downloaded: {bikes_with_images}")
        print(f"Total hero carousel images downloaded: {total_images_downloaded}")
        
        if total_bikes > 0:
            coverage_percentage = (bikes_with_images / total_bikes) * 100
            print(f"Image coverage: {coverage_percentage:.1f}%")
        
        if brand_stats:
            print("\nBy Brand:")
            for brand, stats in brand_stats.items():
                avg_images = stats['images'] / stats['bikes'] if stats['bikes'] > 0 else 0
                print(f"  {brand}: {stats['bikes']} bikes, {stats['images']} images (avg: {avg_images:.1f} per bike)")
        
        # Show folder structure
        if os.path.exists(self.images_base_dir):
            print(f"\nImages saved in: {os.path.abspath(self.images_base_dir)}/")
            for brand in brand_stats.keys():
                brand_path = os.path.join(self.images_base_dir, brand)
                if os.path.exists(brand_path):
                    bike_folders = [d for d in os.listdir(brand_path) if os.path.isdir(os.path.join(brand_path, d))]
                    print(f"  {brand}/: {len(bike_folders)} bike folders")
        
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
        scraper.print_image_summary(bikes) # Added this line to print image summary
    else:
        print("No bikes were scraped. Check the logs for errors.")

if __name__ == "__main__":
    main() 