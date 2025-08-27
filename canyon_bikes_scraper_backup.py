#!/usr/bin/env python3
"""
Canyon Bikes Scraper - Complete Implementation
Scrapes Canyon road bikes from the Dutch website with intelligent predictions
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

class CanyonBikeScraper:
    def __init__(self):
        self.base_url = "https://www.canyon.com"
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
                logging.FileHandler('canyon_scraper.log'),
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
            response = self.session.get(detail_url, timeout=15)
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

    def extract_bike_series_links(self, soup):
        """Extract bike series/category links from Canyon main page"""
        series_links = {}
        
        try:
            # Look for product tiles that link to series pages
            product_tiles = soup.select('.js-productTile')
            
            for tile in product_tiles:
                links = tile.select('a[href]')
                if links:
                    href = links[0].get('href')
                    
                    # Get series name from title or href
                    titles = tile.select('.categorySlider__tileTitle, .productTile__title, h1, h2, h3, h4')
                    if titles:
                        series_name = titles[0].get_text(strip=True)
                    else:
                        # Extract from URL
                        series_name = href.split('/')[-2] if href else "Unknown"
                    
                    if href and href not in ['/nl-nl/racefietsen/endurance-racefietsen/', '/nl-nl/racefietsen/wielrenfietsen/', '/nl-nl/racefietsen/aero-racefietsen/']:
                        continue
                        
                    full_url = urljoin(self.base_url, href)
                    series_links[series_name] = full_url
            
            # Also look for direct series links
            series_selectors = [
                'a[href*="endurance"]',
                'a[href*="ultimate"]', 
                'a[href*="aeroad"]',
                'a[href*="speedmax"]',
                'a[href*="inflite"]'
            ]
            
            for selector in series_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    href = elem.get('href')
                    if href and 'racefietsen' in href:
                        series_name = href.split('/')[-2] if href.endswith('/') else href.split('/')[-1]
                        full_url = urljoin(self.base_url, href)
                        series_links[series_name] = full_url
            
            return series_links
            
        except Exception as e:
            self.logger.error(f"Error extracting bike series links: {e}")
            return {}

    def extract_bikes_from_series(self, series_name, series_url):
        """Extract individual bike links from a Canyon series page"""
        bikes = []
        
        try:
            self.logger.info(f"Fetching series page: {series_url}")
            response = self.session.get(series_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for individual bike links
            bike_links = soup.select('a[href*=".html"]')
            
            for link in bike_links:
                href = link.get('href')
                if href and href.endswith('.html') and 'racefietsen' in href:
                    # Extract bike name
                    bike_name = link.get_text(strip=True)
                    if not bike_name:
                        # Try to extract from surrounding elements
                        parent = link.parent
                        if parent:
                            name_elements = parent.select('.product-name, .bike-name, h1, h2, h3, h4')
                            if name_elements:
                                bike_name = name_elements[0].get_text(strip=True)
                    
                    if not bike_name:
                        # Extract from URL as fallback
                        bike_name = href.split('/')[-1].replace('.html', '').replace('-', ' ').title()
                    
                    full_url = urljoin(self.base_url, href)
                    
                    bike_info = {
                        'name': bike_name,
                        'url': href,
                        'full_url': full_url,
                        'series': series_name,
                        'brand': 'Canyon'
                    }
                    
                    bikes.append(bike_info)
            
            # Remove duplicates by URL
            unique_bikes = []
            seen_urls = set()
            
            for bike in bikes:
                if bike['url'] not in seen_urls:
                    unique_bikes.append(bike)
                    seen_urls.add(bike['url'])
            
            self.logger.info(f"Found {len(unique_bikes)} unique bikes in series: {series_name}")
            return unique_bikes
            
        except Exception as e:
            self.logger.error(f"Error extracting bikes from series {series_name}: {e}")
            return []

    def extract_bike_details(self, bike_info):
        """Extract detailed information from individual Canyon bike page"""
        try:
            url = bike_info.get('url', '')
            self.logger.info(f"Fetching bike details from: {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract bike name (more detailed)
            name = self.extract_canyon_name(soup)
            if name:
                bike_info['name'] = name
            
            # Extract price
            price = self.extract_canyon_price(soup)
            if price:
                bike_info['price'] = price
            
            # Extract specifications
            specifications = self.extract_canyon_specifications(soup)
            if specifications:
                bike_info['specifications'] = specifications
            
            # Extract description
            description = self.extract_canyon_description(soup)
            if description:
                bike_info['description'] = description
            
            # Extract images
            images = self.extract_canyon_images(soup, bike_info)
            if images:
                bike_info['hero_images'] = images
            
            # Set category based on URL structure
            bike_info['category'] = self.determine_canyon_category_from_url(url)
            
            # Extract SKU
            sku = self.extract_sku_from_url(url)
            if sku:
                bike_info['sku'] = sku
            
            # Extract available colors
            colors = self.extract_canyon_colors(soup)
            if colors:
                bike_info['colors'] = colors
                # Also create a simple color list for easier processing
                bike_info['color_names'] = [color['name'] for color in colors]
                bike_info['color_ids'] = [color['id'] for color in colors]
            
            return bike_info
            
        except Exception as e:
            self.logger.error(f"Error extracting bike details for {bike_info.get('name', 'Unknown')}: {e}")
            return None

    def extract_canyon_name(self, soup):
        """Extract bike name from Canyon page"""
        # Look for product title in Canyon's structure
        selectors = [
            'h1',
            '.pdpDetailHero h1',
            '.productDetailHero__productTitle',
            'h1[class*="productTitle"]',
            'h1[class*="product-title"]',
            '.product-name h1'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                name = elements[0].get_text(strip=True)
                if name and len(name) > 3:
                    return name
        
        return None

    def extract_canyon_price(self, soup):
        """Extract price from Canyon page"""
        # Look for price in Canyon's structure
        price_text = None
        
        # Try multiple selectors for price
        price_selectors = [
            '.price',
            '.pdpDetailHero .price',
            '.price-current',
            '.price__current',
            '[class*="price"]'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            if elements:
                price_text = elements[0].get_text(strip=True)
                break
        
        # Also try to find price in the text content
        if not price_text:
            # Look for Euro symbol followed by price pattern
            text_content = soup.get_text()
            import re
            price_patterns = [
                r'(\d+\.?\d*)\s*€',  # "1.849 €"
                r'€\s*(\d+\.?\d*)',  # "€ 1849"
                r'(\d+,\d+)\s*€',    # "1,849 €"
                r'€\s*(\d+,\d+)'     # "€ 1,849"
            ]
            
            for pattern in price_patterns:
                matches = re.findall(pattern, text_content)
                if matches:
                    price_str = matches[0].replace('.', '').replace(',', '.')
                    try:
                        return float(price_str)
                    except:
                        return matches[0]
        
        if price_text:
            # Extract numeric price from text
            import re
            price_match = re.search(r'[\d.,]+', price_text.replace('€', ''))
            if price_match:
                try:
                    price_str = price_match.group().replace('.', '').replace(',', '.')
                    return float(price_str)
                except:
                    return price_text
        
        return None

    def extract_canyon_specifications(self, soup):
        """Extract detailed Dutch specifications from Canyon bike page"""
        specs = {}
        
        try:
            # Initialize all required specification fields
            required_specs = {
                'Frame': '', 'Framefit': '', 'Gewicht': '', 'Gewichtslimiet': '',
                'Shifter': '', 'Voorderailleur': '', 'Achterderailleur': '', 
                'Crankstel': '', 'Bottom_bracket': '', 'Cassette': '', 'Ketting': '',
                'Pedaal': '', 'Maximale_maat_kettingblad': '', 'Naaf_voor': '',
                'As_voorwiel': '', 'Naaf_achter': '', 'Velg': '', 'Buitenband': '',
                'Maximale_bandenmaat': '', 'Zadel': '', 'Zadelpen': '', 'Stuur': '',
                'Stuurlint': '', 'Stuurpen': '', 'Balhoofdstel': '', 'Rem': '',
                'Shifter_speed': '', 'Material': '', 'Weight': ''
            }
            
            # Specification mapping from various Dutch/English terms to our standard names
            spec_mapping = {
                # Frame specifications
                'frame': 'Frame', 'kader': 'Frame', 'frameset': 'Frame',
                'framefit': 'Framefit', 'frame fit': 'Framefit',
                'gewicht': 'Gewicht', 'weight': 'Weight', 'massa': 'Gewicht',
                'gewichtslimiet': 'Gewichtslimiet', 'weight limit': 'Gewichtslimiet',
                'maximum weight': 'Gewichtslimiet', 'max gewicht': 'Gewichtslimiet',
                
                # Drivetrain
                'shifter': 'Shifter', 'schakelhendel': 'Shifter', 'schakelaar': 'Shifter',
                'voorderailleur': 'Voorderailleur', 'front derailleur': 'Voorderailleur',
                'achterderailleur': 'Achterderailleur', 'rear derailleur': 'Achterderailleur',
                'derailleur achter': 'Achterderailleur', 'derailleur voor': 'Voorderailleur',
                'crankstel': 'Crankstel', 'crankset': 'Crankstel', 'crank': 'Crankstel',
                'bottom bracket': 'Bottom_bracket', 'trapas': 'Bottom_bracket',
                'cassette': 'Cassette', 'tandwielcassette': 'Cassette',
                'ketting': 'Ketting', 'chain': 'Ketting',
                'pedaal': 'Pedaal', 'pedal': 'Pedaal', 'pedalen': 'Pedaal',
                'kettingblad': 'Maximale_maat_kettingblad', 'chainring': 'Maximale_maat_kettingblad',
                
                # Wheels & Tires
                'naaf voor': 'Naaf_voor', 'front hub': 'Naaf_voor', 'voornaaf': 'Naaf_voor',
                'as voorwiel': 'As_voorwiel', 'front axle': 'As_voorwiel', 'vooras': 'As_voorwiel',
                'naaf achter': 'Naaf_achter', 'rear hub': 'Naaf_achter', 'achternaaf': 'Naaf_achter',
                'velg': 'Velg', 'rim': 'Velg', 'velgen': 'Velg',
                'buitenband': 'Buitenband', 'tire': 'Buitenband', 'band': 'Buitenband',
                'bandenmaaat': 'Maximale_bandenmaat', 'tire size': 'Maximale_bandenmaat',
                'max tire': 'Maximale_bandenmaat', 'max band': 'Maximale_bandenmaat',
                
                # Cockpit
                'zadel': 'Zadel', 'saddle': 'Zadel', 'zitting': 'Zadel',
                'zadelpen': 'Zadelpen', 'seatpost': 'Zadelpen', 'zadelstam': 'Zadelpen',
                'stuur': 'Stuur', 'handlebar': 'Stuur', 'handlebars': 'Stuur',
                'stuurlint': 'Stuurlint', 'bar tape': 'Stuurlint', 'tape': 'Stuurlint',
                'stuurpen': 'Stuurpen', 'stem': 'Stuurpen', 'voorstam': 'Stuurpen',
                'balhoofdstel': 'Balhoofdstel', 'headset': 'Balhoofdstel',
                
                # Brakes & Other
                'rem': 'Rem', 'brake': 'Rem', 'remmen': 'Rem', 'brakes': 'Rem',
                'speed': 'Shifter_speed', 'versnellingen': 'Shifter_speed',
                'aantal versnellingen': 'Shifter_speed',
                
                # Material
                'material': 'Material', 'materiaal': 'Material'
            }
            
            # Method 1: Look for specification tables and sections
            spec_selectors = [
                'table tr', '.spec-table tr', '.specifications tr',
                '.component-table tr', '.tech-specs tr', '.bike-specs tr',
                '[class*="spec"] tr', '[class*="component"] tr',
                '.product-specs tr', '.details-table tr'
            ]
            
            for selector in spec_selectors:
                rows = soup.select(selector)
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        # Clean up the key
                        key = key.replace(':', '').replace('-', ' ').strip()
                        
                        if key and value and len(value) < 200:
                            # Map to our standard specification names
                            for pattern, std_name in spec_mapping.items():
                                if pattern in key:
                                    required_specs[std_name] = value
                                    break
            
            # Method 2: Look for definition lists and structured data
            dl_elements = soup.find_all('dl')
            for dl in dl_elements:
                dt_elements = dl.find_all('dt')
                dd_elements = dl.find_all('dd')
                for dt, dd in zip(dt_elements, dd_elements):
                    key = dt.get_text(strip=True).lower()
                    value = dd.get_text(strip=True)
                    
                    key = key.replace(':', '').replace('-', ' ').strip()
                    
                    if key and value:
                        for pattern, std_name in spec_mapping.items():
                            if pattern in key:
                                required_specs[std_name] = value
                                break
            
            # Method 3: Extract from page text using patterns
            page_text = soup.get_text()
            
            # Extract material from known keywords
            material_keywords = ['Carbon CFR', 'Carbon CF SLX', 'Carbon CF', 'Aluminium AL', 'Carbon', 'Aluminium']
            for keyword in material_keywords:
                if keyword in page_text and not required_specs['Material']:
                    required_specs['Material'] = keyword
                    break
            
            # Extract weight using regex
            import re
            weight_pattern = r'(\d+[,.]?\d*)\s*kg'
            weight_matches = re.findall(weight_pattern, page_text)
            if weight_matches and not required_specs['Gewicht']:
                required_specs['Gewicht'] = f"{weight_matches[0].replace(',', '.')} kg"
                required_specs['Weight'] = required_specs['Gewicht']
            
            # Extract speed count (number of gears)
            speed_pattern = r'(\d+)\s*(?:speed|versnellingen|Speed)'
            speed_matches = re.findall(speed_pattern, page_text)
            if speed_matches and not required_specs['Shifter_speed']:
                required_specs['Shifter_speed'] = f"{speed_matches[0]} speed"
            
            # Try to get detailed component specifications from onderdelen section
            try:
                onderdelen_specs = self.extract_onderdelen_specifications(soup, '')
                for spec_key, spec_value in onderdelen_specs.items():
                    if spec_key in required_specs and not required_specs[spec_key]:
                        required_specs[spec_key] = spec_value
                self.logger.info(f"Merged {len(onderdelen_specs)} specifications from onderdelen")
            except Exception as e:
                self.logger.warning(f"Could not extract onderdelen specifications: {e}")
            
            # Clean up empty values and return only non-empty specs
            cleaned_specs = {k: v for k, v in required_specs.items() if v and v.strip()}
            
            return cleaned_specs
            
        except Exception as e:
            self.logger.error(f"Error extracting Canyon specifications: {e}")
            return {}

    def extract_canyon_description(self, soup):
        """Extract description from Canyon bike page"""
        try:
            # Look for description in Canyon's structure
            desc_selectors = [
                '.pdpDetailHero p',
                '.product-description',
                '.product-positioning',
                '.bike-description', 
                '.description p',
                '[class*="description"] p',
                '.product-details p',
                '.productDetailContent p',
                '.hero-description p'
            ]
            
            for selector in desc_selectors:
                elements = soup.select(selector)
                for element in elements:
                    desc = element.get_text(strip=True)
                    if desc and len(desc) > 50:  # Only meaningful descriptions
                        return desc
            
            # Look for longer text paragraphs that might be descriptions
            all_paragraphs = soup.find_all('p')
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 100 and len(text) < 1000:  # Reasonable description length
                    # Skip common non-description text
                    skip_phrases = ['cookie', 'privacy', 'newsletter', 'copyright', 'terms', 'conditions']
                    if not any(phrase in text.lower() for phrase in skip_phrases):
                        return text
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting Canyon description: {e}")
            return ""

    def extract_canyon_images(self, soup, bike_info):
        """Extract images from Canyon bike page"""
        images = []
        
        try:
            # Look for Canyon images in various locations
            img_selectors = [
                'img[src*="canyon"]',
                'img[data-src*="canyon"]',
                'img[src*="dma.canyon.com"]',
                'img[data-src*="dma.canyon.com"]',
                '.productDetailHero img',
                '.productCarousel img',
                '.gallery img'
            ]
            
            found_urls = set()
            
            for selector in img_selectors:
                img_elements = soup.select(selector)
                
                for img in img_elements:
                    src = img.get('src') or img.get('data-src')
                    if src and src not in found_urls:
                        # Ensure full URL
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://www.canyon.com' + src
                        
                        # Check if it's a valid Canyon image
                        if ('canyon.com' in src or 'dma.canyon.com' in src) and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            found_urls.add(src)
            
            # Download and save images
            for img_url in list(found_urls)[:10]:  # Limit to 10 images
                downloaded_img = self.download_canyon_image(img_url, bike_info)
                if downloaded_img:
                    images.append(downloaded_img)
            
            return images
            
        except Exception as e:
            self.logger.error(f"Error extracting Canyon images: {e}")
            return []

    def determine_canyon_category_from_url(self, url):
        """Determine bike category based on Canyon URL structure"""
        url_lower = url.lower()
        
        if 'endurance' in url_lower or 'endurace' in url_lower:
            return 'Endurance'
        elif 'ultimate' in url_lower:
            return 'Race'
        elif 'aeroad' in url_lower or 'aero' in url_lower:
            return 'Aero'
        elif 'speedmax' in url_lower:
            return 'Time Trial'
        elif 'inflite' in url_lower:
            return 'Cyclocross'
        else:
            return 'Road Bikes'

    def download_canyon_image(self, image_url, bike_info):
        """Download Canyon bike image"""
        try:
            if not self.download_images:
                return {'url': image_url, 'local_path': '', 'filename': ''}
            
            # Create filename from URL
            filename = self.get_image_filename_from_url(image_url)
            if not filename:
                return None
            
            # Create directory structure
            bike_name = bike_info.get('name', 'Unknown').replace('/', '_').replace(' ', '_')
            bike_dir = os.path.join(self.images_base_dir, 'Canyon', bike_name)
            os.makedirs(bike_dir, exist_ok=True)
            
            # Save image
            save_path = os.path.join(bike_dir, filename)
            
            if self.download_image(image_url, save_path):
                return {
                    'url': image_url,
                    'local_path': save_path,
                    'filename': filename
                }
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error downloading Canyon image: {e}")
            return None

    def extract_canyon_colors(self, soup):
        """Extract available colors from Canyon bike page"""
        try:
            colors = []
            
            # Find the color picker
            color_picker = soup.find('ul', class_='js-colorPicker')
            if not color_picker:
                return colors
            
            # Find all color items
            color_items = color_picker.find_all('li', class_='colorPicker__colorListItem')
            
            for item in color_items:
                # Skip member access messages (not actual colors)
                if 'memberAccessMessage' in ' '.join(item.get('class', [])):
                    continue
                
                # Find the color button
                color_button = item.find('button', class_='js-color-swatch')
                if not color_button:
                    continue
                
                # Extract color information
                color_id = color_button.get('data-swatch-color-id', '')
                color_name = color_button.get('data-displayvalue', '')
                color_url = color_button.get('data-url', '')
                
                if color_id and color_name:
                    color_info = {
                        'id': color_id,
                        'name': color_name,
                        'url': color_url
                    }
                    colors.append(color_info)
                    
                    self.logger.debug(f"Found color: {color_name} ({color_id})")
            
            return colors
            
        except Exception as e:
            self.logger.error(f"Error extracting colors: {e}")
            return []

    def scrape_canyon_bikes(self):
        """Main scraping method for Canyon bikes"""
        # Canyon road bikes listing URL (Dutch site) with all products shown
        url = "https://www.canyon.com/nl-nl/racefietsen/?srule=sort_master_availability_in-stock-prio&searchredirect=false&start=0&sz=200"
        
        self.logger.info(f"Fetching content from: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all individual bike product links
            all_bike_links = []
            
            # Look for all links on the page
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href')
                if not href:
                    continue
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = self.base_url + href
                
                # Check if this is a valid Canyon bike product page
                if self.is_valid_canyon_bike_url(href):
                    # Extract bike name from link text or surrounding elements
                    bike_name = self.extract_bike_name_from_link(link)
                    
                    bike_info = {
                        'name': bike_name or 'Unknown Bike',
                        'url': href,
                        'base_url': self.get_base_bike_url(href),  # For deduplication
                        'brand': 'Canyon'
                    }
                    
                    all_bike_links.append(bike_info)
            
            self.logger.info(f"Found {len(all_bike_links)} total bike links")
            
            # Remove duplicates by base URL (ignore color variants)
            unique_bikes = []
            seen_base_urls = set()
            
            for bike in all_bike_links:
                base_url = bike['base_url']
                if base_url not in seen_base_urls:
                    unique_bikes.append(bike)
                    seen_base_urls.add(base_url)
                else:
                    self.logger.debug(f"Skipping duplicate: {base_url}")
            
            self.logger.info(f"Found {len(unique_bikes)} unique bikes to process")
            
            # Process each individual bike
            detailed_bikes = []
            
            for i, bike_info in enumerate(unique_bikes, 1):
                bike_name = bike_info.get('name', 'Unknown')
                self.logger.info(f"Processing bike {i}/{len(unique_bikes)}: {bike_name}")
                
                # Extract detailed specifications and data
                detailed_bike = self.extract_bike_details(bike_info)
                
                if detailed_bike:
                    detailed_bikes.append(detailed_bike)
                    self.logger.info(f"Successfully processed {bike_name}")
                else:
                    self.logger.warning(f"Failed to process {bike_name}")
                
                # Add delay between requests
                time.sleep(1)
            
            self.logger.info(f"Successfully processed {len(detailed_bikes)} Canyon bikes")
            
            # Remove duplicates by name while preserving order
            final_bikes = []
            seen_names = set()
            
            for bike in detailed_bikes:
                bike_name = bike.get('name', '')
                if bike_name and bike_name not in seen_names:
                    final_bikes.append(bike)
                    seen_names.add(bike_name)
            
            self.logger.info(f"Successfully scraped {len(final_bikes)} unique Canyon bike models")
            
            return final_bikes
            
        except Exception as e:
            self.logger.error(f"Error scraping Canyon bikes: {e}")
            return []

    def is_valid_canyon_bike_url(self, url):
        """Check if URL is a valid Canyon bike product page"""
        if not url or not isinstance(url, str):
            return False
        
        # Must be a Canyon URL
        if 'canyon.com' not in url:
            return False
        
        # Must be a bike product page (ends with .html, may have query params)
        base_url = url.split('?')[0]  # Remove query parameters for validation
        if not base_url.endswith('.html'):
            return False
        
        # Must be in the racefietsen (road bikes) section
        if '/racefietsen/' not in url:
            return False
        
        # Must have a product ID (number before .html)
        url_parts = base_url.rstrip('.html').split('/')
        if url_parts and url_parts[-1].isdigit():
            product_id = url_parts[-1]
            # Product IDs are typically 4-5 digits
            if len(product_id) >= 4:
                pass  # Valid product ID
            else:
                return False
        else:
            return False
        
        # Exclude blog content and promotional pages
        excluded_patterns = [
            '/blog-content/',
            '/koopgids-',
            '/wielren-blog',
            '/news/',
            '/stories/',
            '/campaign/',
            '/promo/',
            '/service/',
            '/support/'
        ]
        
        for pattern in excluded_patterns:
            if pattern in url:
                return False
        
        return True

    def extract_bike_name_from_link(self, link):
        """Extract bike name from link element"""
        # Try to get text from the link itself
        link_text = link.get_text(strip=True)
        if link_text and len(link_text) > 3 and not link_text.lower() in ['meer', 'more', 'bekijk', 'view', 'shop']:
            return link_text
        
        # Try to find bike name in surrounding elements
        parent = link.parent
        if parent:
            # Look for title elements
            title_elements = parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
            for elem in title_elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 3:
                    return text
            
            # Look for elements with bike/product name classes
            name_elements = parent.find_all(class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['title', 'name', 'product']))
            for elem in name_elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 3:
                    return text
        
        # Extract from URL as last resort
        url = link.get('href', '')
        if url:
            # Remove query parameters for parsing
            base_url = url.split('?')[0]
            
            # Get the bike model name from URL structure
            # Example: /aeroad/cfr/aeroad-cfr-di2/4039.html -> aeroad-cfr-di2
            url_parts = base_url.rstrip('.html').split('/')
            if len(url_parts) >= 2:
                # The bike model is usually the second-to-last part
                bike_model = url_parts[-2]
                if bike_model and not bike_model.isdigit():
                    # Convert URL format to readable name
                    bike_name = bike_model.replace('-', ' ').title()
                    return bike_name
        
        return None

    def get_base_bike_url(self, url):
        """Get base URL without query parameters for deduplication"""
        return url.split('?')[0] if url else url

    def clean_old_files(self, keep_count=3):
        """Move old timestamped files to archive, keeping only the most recent ones in working directories"""
        patterns_and_archive_dirs = [
            ('data/Canyon/canyon_bikes_*.json', 'data/archive/Canyon'),
            ('data/Canyon/canyon_bikes_*.csv', 'data/archive/Canyon'), 
            ('data/Canyon/canyon_bikes_*.xlsx', 'data/archive/Canyon'),
            ('data/wordpress_imports/canyon_bikes_wordpress_*.csv', 'data/archive/wordpress_imports')
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
        brand_dir = 'data/Canyon'
        os.makedirs(brand_dir, exist_ok=True)
        os.makedirs('data', exist_ok=True)  # Keep data root for 'latest' files
        
        # Clean up old files first
        self.clean_old_files()
        
        # Save timestamped versions in brand folder
        json_file = f'{brand_dir}/canyon_bikes_{timestamp}.json'
        csv_file = f'{brand_dir}/canyon_bikes_{timestamp}.csv'
        excel_file = f'{brand_dir}/canyon_bikes_{timestamp}.xlsx'
        
        # Save JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(bikes, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Saved {len(bikes)} bikes to {json_file}")
        
        # Prepare data for CSV/Excel
        csv_data = []
        excluded_track_bikes = 0
        
        for bike in bikes:
            # Skip track bikes (not regular road bikes)
            bike_name = bike.get('name', '').lower()
            bike_url = bike.get('url', '').lower()
            
            if 'track' in bike_name or 'track' in bike_url:
                excluded_track_bikes += 1
                self.logger.info(f"Excluding track bike: {bike.get('name', 'Unknown')}")
                continue
            
            # Get color variants
            colors = bike.get('colors', [])
            
            # If no colors found, create one row with empty variant/color
            if not colors:
                colors = [{'id': '', 'name': '', 'url': ''}]
            
            # Create a separate row for each color variant
            for color in colors:
                row = {
                    'name': bike.get('name', ''),
                    'price': bike.get('price', ''),
                    'category': bike.get('category', ''),
                    'brand': bike.get('brand', 'Canyon'),
                    'url': bike.get('url', ''),
                    'sku': bike.get('sku', ''),
                    'variant': color.get('id', ''),  # Color ID as variant
                    'color': color.get('name', ''),  # Color name as color
                    'description': bike.get('description', '')
                }
                
                # Add specific Dutch specification columns
                specifications = bike.get('specifications', {})
                
                # Add all required specification columns in the specified order
                required_spec_columns = [
                    'Frame', 'Framefit', 'Gewicht', 'Gewichtslimiet', 'Shifter', 
                    'Voorderailleur', 'Achterderailleur', 'Crankstel', 'Bottom_bracket', 
                    'Cassette', 'Ketting', 'Pedaal', 'Maximale_maat_kettingblad',
                    'Naaf_voor', 'As_voorwiel', 'Naaf_achter', 'Velg', 'Buitenband',
                    'Maximale_bandenmaat', 'Zadel', 'Zadelpen', 'Stuur', 'Stuurlint',
                    'Stuurpen', 'Balhoofdstel', 'Rem', 'Shifter_speed'
                ]
                
                # Add each specification column
                for spec_name in required_spec_columns:
                    row[f'spec_{spec_name}'] = specifications.get(spec_name, '')
                
                # Also add the legacy Material and Weight specs for compatibility
                row['spec_Material'] = specifications.get('Material', '')
                row['spec_Weight'] = specifications.get('Weight', '')
                
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
            df.to_csv(csv_file, index=False, encoding='utf-8')
            
            total_bikes = len(bikes)
            exported_bikes = total_bikes - excluded_track_bikes
            self.logger.info(f"Saved {exported_bikes} bikes to {csv_file} ({excluded_track_bikes} track bikes excluded from export)")
            
            # Save Excel
            df.to_excel(excel_file, index=False, engine='openpyxl')
            self.logger.info(f"Saved {exported_bikes} bikes to {excel_file}")
        
        # Also save latest versions (overwrite)
        latest_json = 'data/canyon_bikes_latest.json'
        latest_csv = 'data/canyon_bikes_latest.csv'
        latest_excel = 'data/canyon_bikes_latest.xlsx'
        
        with open(latest_json, 'w', encoding='utf-8') as f:
            json.dump(bikes, f, ensure_ascii=False, indent=2)
        
        if csv_data:
            df.to_csv(latest_csv, index=False, encoding='utf-8')
            df.to_excel(latest_excel, index=False, engine='openpyxl')
        
        self.logger.info(f"Also saved latest versions as {latest_json}, {latest_csv}, and {latest_excel}")
        
        # Automatically generate WordPress-ready CSV for Canyon
        if WORDPRESS_CONVERTER_AVAILABLE and csv_data:
            try:
                self.logger.info("Generating WordPress-ready CSV...")
                wp_file = convert_latest_to_wordpress(brand="canyon", verbose=False)
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
            price_str = str(bike.get('price', ''))
            if price_str and price_str != 'None':
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
                price_str = str(bike.get('price', ''))
                if price_str and price_str != 'None':
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

    def extract_sku_from_url(self, url):
        """Extract SKU/product ID from Canyon URL"""
        try:
            if not url:
                return None
            
            # Remove query parameters
            base_url = url.split('?')[0]
            
            # Extract the number before .html
            # Example: /endurace-allroad/4164.html -> 4164
            if base_url.endswith('.html'):
                # Get the last part after the final /
                url_parts = base_url.rstrip('.html').split('/')
                if url_parts and url_parts[-1].isdigit():
                    return url_parts[-1]
            
            return None
        except Exception as e:
            self.logger.error(f"Error extracting SKU from URL {url}: {e}")
            return None

    def extract_onderdelen_specifications(self, soup, bike_url):
        """Extract detailed specifications from Canyon's dynamic onderdelen (components) section"""
        try:
            # Find the onderdelen button to get the dynamic URL
            onderdelen_button = soup.find('button', class_='js-accordion-toggle-components')
            if not onderdelen_button:
                self.logger.warning("Could not find onderdelen accordion button")
                return {}
            
            # Extract the dynamic URL
            dynamic_url = onderdelen_button.get('data-dynamic-accordion-item-url')
            if not dynamic_url:
                self.logger.warning("Could not find dynamic onderdelen URL")
                return {}
            
            self.logger.info(f"Fetching onderdelen from: {dynamic_url}")
            
            # Fetch the dynamic content
            response = self.session.get(dynamic_url, timeout=15)
            response.raise_for_status()
            
            onderdelen_soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract component specifications
            specs = {}
            
            # Component mapping from Canyon names to our spec fields
            component_mapping = {
                # Drivetrain (Aandrijving)
                'voorderailleur': 'Voorderailleur', 'front derailleur': 'Voorderailleur',
                'achterderailleur': 'Achterderailleur', 'rear derailleur': 'Achterderailleur',
                'derailleur': 'Achterderailleur',  # Default to rear if not specified
                'crankstel': 'Crankstel', 'crankset': 'Crankstel', 'crank': 'Crankstel',
                'bottom bracket': 'Bottom_bracket', 'trapas': 'Bottom_bracket',
                'cassette': 'Cassette', 'tandwielcassette': 'Cassette',
                'chain': 'Ketting', 'ketting': 'Ketting',
                'pedaal': 'Pedaal', 'pedal': 'Pedaal', 'pedalen': 'Pedaal',
                'kettingblad': 'Maximale_maat_kettingblad', 'chainring': 'Maximale_maat_kettingblad',
                
                # Wheels (Wielen)
                'front hub': 'Naaf_voor', 'voornaaf': 'Naaf_voor', 'naaf voor': 'Naaf_voor',
                'front axle': 'As_voorwiel', 'vooras': 'As_voorwiel', 'as voorwiel': 'As_voorwiel',
                'rear hub': 'Naaf_achter', 'achternaaf': 'Naaf_achter', 'naaf achter': 'Naaf_achter',
                'rim': 'Velg', 'velg': 'Velg', 'velgen': 'Velg',
                'tire': 'Buitenband', 'tyre': 'Buitenband', 'band': 'Buitenband', 'buitenband': 'Buitenband',
                
                # Cockpit
                'saddle': 'Zadel', 'zadel': 'Zadel', 'zitting': 'Zadel',
                'seatpost': 'Zadelpen', 'zadelpen': 'Zadelpen', 'zadelstam': 'Zadelpen',
                'handlebar': 'Stuur', 'stuur': 'Stuur', 'handlebars': 'Stuur',
                'bar tape': 'Stuurlint', 'stuurlint': 'Stuurlint', 'tape': 'Stuurlint',
                'stem': 'Stuurpen', 'stuurpen': 'Stuurpen', 'voorstam': 'Stuurpen',
                'headset': 'Balhoofdstel', 'balhoofdstel': 'Balhoofdstel',
                
                # Brakes (Remmen) - excluding shifters for now
                'brake': 'Rem', 'rem': 'Rem', 'remmen': 'Rem', 'brakes': 'Rem'
            }
            
            # Use proper HTML structure to find components
            # Look for component sections with titles and their corresponding component names
            
            # Find all component section items
            component_items = onderdelen_soup.find_all('li', class_='allComponents__sectionSpecListItem')
            
            for item in component_items:
                # Get the component title
                title_div = item.find('div', class_='allComponents__sectionSpecListItemTitle')
                if title_div:
                    component_title = title_div.get_text(strip=True).lower()
                    
                    # Find the component name (first item with --name class)
                    name_item = item.find('li', class_='allComponents__specItemListItem--name')
                    if name_item:
                        component_name = name_item.get_text(strip=True)
                        
                        # Find all feature descriptions for this component
                        feature_items = item.find_all('li', class_='allComponents__specItemListItem--feature')
                        features = [feature.get_text(strip=True) for feature in feature_items if feature.get_text(strip=True)]
                        
                        # For cockpit/stuur, combine name with features for full description
                        if component_title.lower() == 'cockpit' and features:
                            component_description = component_name + "\n" + " ".join(features)
                        else:
                            component_description = component_name
                    
                    # Map component titles to our specification fields
                    title_to_field = {
                            'schakel / remhendel': 'Shifter',
                            'voorderailleur': 'Voorderailleur', 
                            'achterderailleur': 'Achterderailleur',
                            'crankstel': 'Crankstel',
                            'trapas': 'Bottom_bracket',
                            'bottom bracket': 'Bottom_bracket',
                            'cassette': 'Cassette',
                            'ketting': 'Ketting',
                            'chain': 'Ketting',
                            'pedaal': 'Pedaal',
                            'pedalen': 'Pedaal',
                            'kettingblad': 'Maximale_maat_kettingblad',
                            'chainring': 'Maximale_maat_kettingblad',
                            'voornaaf': 'Naaf_voor',
                            'naaf voor': 'Naaf_voor', 
                            'front hub': 'Naaf_voor',
                            'vooras': 'As_voorwiel',
                            'as voorwiel': 'As_voorwiel',
                            'front axle': 'As_voorwiel',
                            'achternaaf': 'Naaf_achter',
                            'naaf achter': 'Naaf_achter',
                            'rear hub': 'Naaf_achter',
                            'velg': 'Velg',
                            'velgen': 'Velg',
                            'rim': 'Velg',
                            'band': 'Buitenband',
                            'buitenband': 'Buitenband',
                            'tire': 'Buitenband',
                            'tyre': 'Buitenband',
                            'zadel': 'Zadel',
                            'saddle': 'Zadel',
                            'zadelpen': 'Zadelpen',
                            'seatpost': 'Zadelpen',
                            'stuur': 'Stuur',
                            'handlebar': 'Stuur',
                            'handlebars': 'Stuur',
                            'stuurlint': 'Stuurlint',
                            'bar tape': 'Stuurlint',
                            'tape': 'Stuurlint',
                            'stuurpen': 'Stuurpen',
                            'stem': 'Stuurpen',
                            'balhoofdstel': 'Balhoofdstel',
                            'headset': 'Balhoofdstel',
                            'rem': 'Rem',
                            'remmen': 'Rem',
                            'brake': 'Rem',
                            'brakes': 'Rem'
                        }
                        
                        # Check if this component title matches any of our fields
                        for title_pattern, spec_field in title_to_field.items():
                            if title_pattern in component_title:
                                # Special handling for shifter - prefer the most complete one and clean up speed info
                                if spec_field == 'Shifter':
                                    # Remove speed information from shifter names
                                    import re
                                    cleaned_name = re.sub(r',\s*\d+[-\s]*speed\b', '', component_description, flags=re.IGNORECASE)
                                    cleaned_name = re.sub(r',\s*\d+s\b', '', cleaned_name, flags=re.IGNORECASE)
                                    cleaned_name = re.sub(r'\b\d+[-\s]*speed\b', '', cleaned_name, flags=re.IGNORECASE)
                                    cleaned_name = re.sub(r'\b\d+s\b', '', cleaned_name, flags=re.IGNORECASE)
                                    cleaned_name = cleaned_name.strip().rstrip(',').strip()
                                    
                                    if spec_field not in specs or len(cleaned_name) > len(specs[spec_field]):
                                        specs[spec_field] = cleaned_name
                                else:
                                    if spec_field not in specs:  # Don't overwrite if already found
                                        specs[spec_field] = component_description
                                break
            
            # Also look for speed count (gear count) in the text
            import re
            speed_patterns = [
                r'(\d+)[-\s]*speed',
                r'(\d+)[-\s]*versnellingen',
                r'(\d+)[-\s]*Speed'
            ]
            
            # Get all text from the onderdelen page for speed matching
            onderdelen_text = onderdelen_soup.get_text().lower()
            
            for pattern in speed_patterns:
                matches = re.findall(pattern, onderdelen_text)
                if matches and 'Shifter_speed' not in specs:
                    speeds = [int(m) for m in matches if m.isdigit()]
                    if speeds:
                        max_speed = max(speeds)
                        if max_speed > 5:  # Reasonable range for bike speeds
                            specs['Shifter_speed'] = f"{max_speed} speed"
                            break
            
            # Look for specific component categories
            category_headers = onderdelen_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            current_category = None
            
            for header in category_headers:
                header_text = header.get_text(strip=True).lower()
                if 'aandrijving' in header_text:
                    current_category = 'drivetrain'
                elif 'remmen' in header_text:
                    current_category = 'brakes'
                elif 'wielen' in header_text:
                    current_category = 'wheels'
                elif 'cockpit' in header_text:
                    current_category = 'cockpit'
            
            self.logger.info(f"Extracted {len(specs)} component specifications from onderdelen")
            return specs
            
        except Exception as e:
            self.logger.error(f"Error extracting onderdelen specifications: {e}")
            return {}

def main():
    """Main function"""
    scraper = CanyonBikeScraper()
    
    # Scrape bikes
    bikes = scraper.scrape_canyon_bikes()
    
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