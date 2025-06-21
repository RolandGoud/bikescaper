# Manufacturer-specific scrapers
import re
import time
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from base_scraper import BaseBikeScraper
from data_models import Bike, BikePrice, BikeSpecification, BikeAvailability, BikeReview, BikeImage
from utils import TextUtils, WebUtils
import logging

logger = logging.getLogger(__name__)

class TrekScraper(BaseBikeScraper):
    """Scraper for Trek bikes"""
    
    def get_bike_urls(self) -> List[str]:
        """Get all Trek bike URLs - focusing on specific bike detail pages"""
        urls = []
        
        try:
            # Trek specific category URLs for individual bikes
            category_urls = [
                f"{self.bikes_url}road-bikes/",
                f"{self.bikes_url}mountain-bikes/",
                f"{self.bikes_url}hybrid-bikes/",
                f"{self.bikes_url}electric-bikes/",
                f"{self.bikes_url}kids-bikes/"
            ]
            
            for category_url in category_urls:
                try:
                    logger.info(f"Searching Trek category: {category_url}")
                    soup = self.get_page_content(category_url)
                    
                    if soup:
                        # Look for specific bike model links (not category links)
                        potential_links = soup.find_all('a', href=True)
                        
                        for link in potential_links:
                            href = link.get('href')
                            if href and self._is_trek_bike_detail_url(href):
                                full_url = WebUtils.normalize_url(href, self.base_url)
                                if full_url not in urls:
                                    urls.append(full_url)
                                    logger.debug(f"Found Trek bike URL: {full_url}")
                    
                    time.sleep(1)  # Rate limiting between categories
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape Trek category {category_url}: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to get Trek bike URLs: {str(e)}")
        
        logger.info(f"Found {len(urls)} potential Trek bike detail URLs")
        return urls[:50]  # Limit for testing
    
    def scrape_single_bike(self, url: str) -> Optional[Bike]:
        """Scrape a single Trek bike from detail page"""
        try:
            soup = self.get_page_content(url)
            if not soup:
                return None
            
            # Skip if this is a category page (similar to Giant fix)
            if any(cat in url for cat in ['/c/', 'category', 'search', 'overview']):
                logger.debug(f"Skipping Trek category page: {url}")
                return None
            
            # Extract basic information
            basic_info = self.extract_basic_info(soup, url)
            
            # Trek-specific model extraction - try multiple selectors
            model_name = ""
            
            # Try different Trek-specific selectors for model name
            model_selectors = [
                'h1.pdp__title',
                '.pdp-hero__title h1',
                '.product-title',
                'h1[data-testid="pdp-product-name"]',
                '.bike-name',
                'h1'
            ]
            
            for selector in model_selectors:
                model_element = soup.select_one(selector)
                if model_element:
                    model_name = TextUtils.clean_text(model_element.get_text())
                    if model_name and not any(skip in model_name.lower() for skip in ['shop', 'category', 'bikes']):
                        break
            
            # Extract category from URL structure
            category = ""
            if '/road-bikes/' in url:
                category = 'Road'
            elif '/mountain-bikes/' in url:
                category = 'Mountain'
            elif '/hybrid-bikes/' in url:
                category = 'Hybrid'
            elif '/electric-bikes/' in url:
                category = 'Electric'
            elif '/kids-bikes/' in url:
                category = 'Kids'
            
            basic_info['model'] = model_name
            basic_info['category'] = category
            
            # Create bike object
            bike = Bike(
                manufacturer=basic_info['manufacturer'],
                model=basic_info['model'],
                category=basic_info['category'],
                url=url
            )
            
            # Extract detailed information using Trek-specific methods
            bike.pricing = self.extract_trek_pricing(soup)
            bike.specifications = self.extract_trek_specifications(soup)
            bike.availability = self.extract_trek_availability(soup)
            bike.reviews = self.extract_reviews(soup)
            bike.images = self.extract_images(soup, bike.model)
            
            # Trek-specific description
            desc_selectors = ['.pdp-hero__description', '.product-description', '.bike-description', '.overview', '.pdp-story']
            for selector in desc_selectors:
                desc_element = soup.select_one(selector)
                if desc_element:
                    bike.description = TextUtils.clean_text(desc_element.get_text())
                    break
            
            logger.info(f"Successfully scraped Trek bike: {bike.model}")
            return bike
            
        except Exception as e:
            logger.error(f"Failed to scrape Trek bike from {url}: {str(e)}")
            return None
    
    def _is_bike_url(self, url: str) -> bool:
        """Check if URL is a valid bike product page"""
        return ('/bikes/' in url and 
                not any(exclude in url for exclude in ['category', 'search', 'filter', '#', '?']))
    
    def _is_trek_bike_detail_url(self, url: str) -> bool:
        """Check if URL is a specific Trek bike detail page (not category page)"""
        if not url:
            return False
            
        # Convert relative URLs to full URLs for pattern matching
        if url.startswith('/'):
            url = f"{self.base_url}{url}"
        
        # More flexible patterns for Trek bike URLs
        import re
        
        # Trek bike URLs can follow various patterns:
        # /us/en_US/bikes/category/subcategory/model-name/p/model-id/
        # /us/en_US/bikes/electra-bikes/cruiser-bikes/super-deluxe-tandem-7i/p/24579/
        
        # Check for essential characteristics of Trek bike detail pages
        has_bikes_path = '/bikes/' in url
        
        # Check if it has the /p/number pattern (most reliable indicator)
        has_model_path = '/p/' in url and bool(re.search(r'/p/\d+/?$', url))
        
        # Check if it's NOT a category page
        not_category = not any(exclude in url.lower() for exclude in [
            '/c/', 'category', 'search', 'filter', 'overview',
            'accessories', 'parts'
        ])
        
        # Exclude bare category URLs like /bikes/road-bikes/ (ends with category name)
        not_bare_category = not bool(re.search(r'/bikes/[^/]+/?$', url))
        
        # Also look for Trek-style URLs with deep model structure
        model_pattern = bool(re.search(r'/bikes/[^/]+/[^/]+/[a-zA-Z0-9\-]+', url))
        
        return (has_bikes_path and (has_model_path or (model_pattern and not_bare_category)) and not_category)
    
    def extract_trek_pricing(self, soup: BeautifulSoup) -> BikePrice:
        """Extract Trek-specific pricing information"""
        pricing = BikePrice()
        
        # Trek-specific price selectors
        price_selectors = [
            '.pdp-pricing__price',
            '.product-price',
            '.price-current',
            '[data-testid="price"]',
            '.pricing-module__price',
            '.price'
        ]
        
        for selector in price_selectors:
            price_elements = soup.select(selector)
            for element in price_elements:
                text = element.get_text(strip=True)
                price, currency = TextUtils.extract_price(text)
                if price:
                    pricing.price = price
                    pricing.currency = currency
                    break
            if pricing.price:
                break
        
        return pricing
    
    def extract_trek_specifications(self, soup: BeautifulSoup) -> BikeSpecification:
        """Extract Trek-specific specifications"""
        specs = BikeSpecification()
        
        # Look for Trek specifications sections
        spec_sections = soup.select('.pdp-specs, .specifications, .spec-table, [data-testid="specifications"]')
        
        for section in spec_sections:
            # Check for structured data in tables or lists
            spec_items = section.select('tr, .spec-item, .specification-row, dt')
            
            for item in spec_items:
                text = item.get_text().lower()
                
                # Frame material
                if 'frame' in text:
                    if 'carbon' in text or 'oclv' in text:  # Trek's OCLV Carbon
                        specs.frame_material = 'Carbon'
                    elif 'aluminum' in text or 'alpha' in text:  # Trek's Alpha Aluminum
                        specs.frame_material = 'Aluminum'
                    elif 'steel' in text:
                        specs.frame_material = 'Steel'
                
                # Weight
                if 'weight' in text:
                    weight = TextUtils.extract_weight(item.get_text())
                    if weight:
                        specs.weight = weight
                
                # Wheel size
                if 'wheel' in text or 'tire' in text:
                    if '700c' in text:
                        specs.wheel_size = '700c'
                    elif '650b' in text:
                        specs.wheel_size = '650b'
                    elif '29' in text:
                        specs.wheel_size = '29"'
                    elif '27.5' in text:
                        specs.wheel_size = '27.5"'
                
                # Gears/drivetrain
                if 'speed' in text or 'gear' in text:
                    import re
                    speed_match = re.search(r'(\d+)\s*(?:speed|gear)', text)
                    if speed_match:
                        specs.gears = f"{speed_match.group(1)} speed"
        
        return specs
    
    def extract_trek_availability(self, soup: BeautifulSoup) -> BikeAvailability:
        """Extract Trek-specific availability information"""
        availability = BikeAvailability()
        
        # Check for size selection elements
        size_elements = soup.select('.size-selector, .sizes, [data-testid="size"], .size-option')
        sizes = []
        for element in size_elements:
            size_text = element.get_text()
            # Extract common bike sizes
            import re
            size_matches = re.findall(r'\b(XS|S|M|ML|L|XL|XXL|\d{2,3}cm)\b', size_text, re.IGNORECASE)
            sizes.extend(size_matches)
        
        availability.available_sizes = list(set(sizes))
        
        # Check for color options
        color_elements = soup.select('.color-selector, .colors, [data-testid="color"], .color-option')
        colors = []
        for element in color_elements:
            color_text = element.get_text(strip=True)
            if color_text and len(color_text) < 50:  # Reasonable color name length
                colors.append(color_text)
        
        availability.available_colors = list(set(colors))
        
        return availability

class SpecializedScraper(BaseBikeScraper):
    """Scraper for Specialized bikes"""
    
    def get_bike_urls(self) -> List[str]:
        """Get all Specialized bike URLs"""
        urls = []
        
        try:
            # Start from main bikes page
            soup = self.get_page_content(self.bikes_url)
            
            if soup:
                # Look for bike product links
                bike_links = soup.select('a[href*="/bikes/"]')
                for link in bike_links:
                    href = link.get('href')
                    if href:
                        full_url = WebUtils.normalize_url(href, self.base_url)
                        if full_url not in urls and self._is_bike_url(full_url):
                            urls.append(full_url)
                
                # Check for pagination or "load more" functionality
                next_links = soup.select('a[href*="page="], .load-more, .next-page')
                # Implementation for handling pagination would go here
        
        except Exception as e:
            logger.error(f"Failed to get Specialized bike URLs: {str(e)}")
        
        return urls[:50]  # Limit for testing
    
    def scrape_single_bike(self, url: str) -> Optional[Bike]:
        """Scrape a single Specialized bike"""
        try:
            soup = self.get_page_content(url)
            if not soup:
                return None
            
            # Extract basic information
            basic_info = self.extract_basic_info(soup, url)
            
            # Specialized-specific model extraction
            model_element = soup.select_one('h1.pdp-product-name, .product-title')
            if model_element:
                basic_info['model'] = TextUtils.clean_text(model_element.get_text())
            
            # Create bike object
            bike = Bike(
                manufacturer=basic_info['manufacturer'],
                model=basic_info['model'],
                category=basic_info['category'],
                url=url
            )
            
            # Extract detailed information
            bike.pricing = self.extract_pricing(soup)
            bike.specifications = self.extract_specialized_specs(soup)
            bike.availability = self.extract_availability(soup)
            bike.reviews = self.extract_reviews(soup)
            bike.images = self.extract_images(soup, bike.model)
            
            return bike
            
        except Exception as e:
            logger.error(f"Failed to scrape Specialized bike from {url}: {str(e)}")
            return None
    
    def extract_specialized_specs(self, soup: BeautifulSoup) -> BikeSpecification:
        """Extract Specialized-specific specifications"""
        specs = BikeSpecification()
        
        # Look for spec tables or lists
        spec_tables = soup.select('.spec-table, .specifications-table')
        for table in spec_tables:
            rows = table.select('tr')
            for row in rows:
                cells = row.select('td, th')
                if len(cells) >= 2:
                    key = cells[0].get_text().strip().lower()
                    value = cells[1].get_text().strip()
                    
                    if 'frame' in key and 'material' in key:
                        specs.frame_material = value
                    elif 'weight' in key:
                        specs.weight = value
                    elif 'wheel' in key or 'tire' in key:
                        if 'size' in key:
                            specs.wheel_size = value
        
        return specs
    
    def _is_bike_url(self, url: str) -> bool:
        """Check if URL is a valid Specialized bike product page"""
        return ('/bikes/' in url and 
                not any(exclude in url for exclude in ['category', 'search', 'filter']))

class GiantScraper(BaseBikeScraper):
    """Scraper for Giant bikes"""
    
    def get_bike_urls(self) -> List[str]:
        """Get all Giant bike URLs - focusing on specific bike detail pages"""
        urls = []
        
        try:
            # Start with main bikes page
            soup = self.get_page_content(self.bikes_url)
            
            if soup:
                # First, get all category pages to find bike listings
                category_urls = [
                    f"{self.bikes_url}/fietsen/e-bikes",
                    f"{self.bikes_url}/fietsen/racefietsen", 
                    f"{self.bikes_url}/fietsen/mountainbikes",
                    f"{self.bikes_url}/fietsen/gravel-cross-en-adventure",
                    f"{self.bikes_url}/fietsen/stads-en-toerfietsen",
                    f"{self.bikes_url}/fietsen/kinderfietsen"
                ]
                
                for category_url in category_urls:
                    try:
                        logger.info(f"Searching category: {category_url}")
                        category_soup = self.get_page_content(category_url)
                        
                        if category_soup:
                            # Look for specific bike model links - these often have product names in href
                            potential_links = category_soup.find_all('a', href=True)
                            
                            for link in potential_links:
                                href = link.get('href')
                                if href:
                                    # Look for bike detail page patterns
                                    if self._is_bike_detail_url(href):
                                        full_url = WebUtils.normalize_url(href, self.base_url)
                                        if full_url not in urls:
                                            urls.append(full_url)
                                            logger.debug(f"Found bike URL: {full_url}")
                            
                            # Also look for "View Details" or similar buttons/links
                            detail_links = category_soup.select('a[href*="bikes-"], a[title*="bekijk"], a[title*="view"], a[class*="detail"], a[class*="product-link"]')
                            for link in detail_links:
                                href = link.get('href')
                                if href and self._is_bike_detail_url(href):
                                    full_url = WebUtils.normalize_url(href, self.base_url)
                                    if full_url not in urls:
                                        urls.append(full_url)
                                        logger.debug(f"Found detail URL: {full_url}")
                        
                        time.sleep(0.5)  # Rate limiting
                        
                    except Exception as e:
                        logger.warning(f"Failed to scrape category {category_url}: {str(e)}")
                        continue
                
                # Try to find bikes on the main page as well
                main_bike_links = soup.find_all('a', href=True)
                for link in main_bike_links:
                    href = link.get('href')
                    if href and self._is_bike_detail_url(href):
                        full_url = WebUtils.normalize_url(href, self.base_url)
                        if full_url not in urls:
                            urls.append(full_url)
        
        except Exception as e:
            logger.error(f"Failed to get Giant bike URLs: {str(e)}")
        
        logger.info(f"Found {len(urls)} potential bike detail URLs")
        return urls[:100]  # Increased limit for more comprehensive scraping
    
    def scrape_single_bike(self, url: str) -> Optional[Bike]:
        """Scrape a single Giant bike from detail page"""
        try:
            soup = self.get_page_content(url)
            if not soup:
                return None
            
            # Skip if this is a category page
            if any(cat in url for cat in ['/fietsen/', '/e-bikes/', '/racefietsen/', '/mountainbikes/']):
                logger.debug(f"Skipping category page: {url}")
                return None
            
            # Extract basic information
            basic_info = self.extract_basic_info(soup, url)
            
            # Giant-specific model extraction from breadcrumbs or title
            model_name = ""
            
            # Try breadcrumb navigation for model name
            breadcrumb = soup.select_one('nav[aria-label="breadcrumb"] .active, .breadcrumb .active')
            if breadcrumb:
                model_name = TextUtils.clean_text(breadcrumb.get_text())
            
            # Try page title/heading
            if not model_name:
                title_selectors = ['h1', '.product-title', '.bike-title', '[class*="title"]']
                for selector in title_selectors:
                    title_element = soup.select_one(selector)
                    if title_element:
                        model_name = TextUtils.clean_text(title_element.get_text())
                        break
            
            # Extract category from URL or breadcrumbs
            category = ""
            if '/e-bikes/' in url or 'elektrische' in url.lower():
                category = 'E-Bike'
            elif '/racefietsen/' in url:
                category = 'Road Bike'
            elif '/mountainbikes/' in url:
                category = 'Mountain Bike'
            elif '/gravel' in url:
                category = 'Gravel'
            
            basic_info['model'] = model_name
            basic_info['category'] = category
            
            # Create bike object
            bike = Bike(
                manufacturer=basic_info['manufacturer'],
                model=basic_info['model'],
                category=basic_info['category'],
                url=url
            )
            
            # Extract detailed information
            bike.pricing = self.extract_giant_pricing(soup)
            bike.specifications = self.extract_giant_specifications(soup)
            bike.availability = self.extract_giant_availability(soup)
            bike.reviews = self.extract_reviews(soup)
            bike.images = self.extract_images(soup, bike.model)
            
            # Extract description
            desc_selectors = ['.description', '.product-description', '.overview', '[class*="description"]']
            for selector in desc_selectors:
                desc_element = soup.select_one(selector)
                if desc_element:
                    bike.description = TextUtils.clean_text(desc_element.get_text())
                    break
            
            logger.info(f"Successfully scraped Giant bike: {bike.model}")
            return bike
            
        except Exception as e:
            logger.error(f"Failed to scrape Giant bike from {url}: {str(e)}")
            return None
    
    def _is_bike_url(self, url: str) -> bool:
        """Check if URL is a valid Giant bike product page"""
        return (('/bike' in url or '/fietsen/' in url) and 
                '/nl/' in url and  # Ensure it's Dutch site
                not any(exclude in url for exclude in ['category', 'search', '/fietsen?', '/fietsen#', 'accessories', 'accessoires']))
    
    def _is_bike_detail_url(self, url: str) -> bool:
        """Check if URL is a specific bike detail page (not category page)"""
        if not url:
            return False
    
    def extract_giant_pricing(self, soup: BeautifulSoup) -> BikePrice:
        """Extract Giant-specific pricing information"""
        pricing = BikePrice()
        
        # Look for price elements specific to Giant's website structure
        price_selectors = [
            '.price', '.product-price', '[class*="price"]',
            '.cost', '.product-cost', '[data-price]',
            '.current-price', '.final-price'
        ]
        
        for selector in price_selectors:
            price_elements = soup.select(selector)
            for element in price_elements:
                text = element.get_text(strip=True)
                price, currency = TextUtils.extract_price(text)
                if price:
                    pricing.price = price
                    pricing.currency = currency
                    break
            if pricing.price:
                break
        
        return pricing
    
    def extract_giant_specifications(self, soup: BeautifulSoup) -> BikeSpecification:
        """Extract Giant-specific specifications"""
        specs = BikeSpecification()
        
        # Look for specifications table/section
        spec_sections = soup.select('.specifications, .specs, .tech-specs, [class*="spec"]')
        
        for section in spec_sections:
            # Check for structured data in tables or lists
            spec_rows = section.select('tr, li, dt, .spec-row')
            
            for row in spec_rows:
                text = row.get_text().lower()
                
                # Frame material
                if 'frame' in text:
                    if 'carbon' in text or 'composite' in text:
                        specs.frame_material = 'Carbon'
                    elif 'aluminum' in text or 'aluminium' in text:
                        specs.frame_material = 'Aluminum'
                    elif 'steel' in text:
                        specs.frame_material = 'Steel'
                
                # Weight
                if 'gewicht' in text or 'weight' in text:
                    weight = TextUtils.extract_weight(row.get_text())
                    if weight:
                        specs.weight = weight
                
                # Wheel size
                if 'wielmaat' in text or 'wheel' in text:
                    if '700c' in text:
                        specs.wheel_size = '700c'
                    elif '650b' in text:
                        specs.wheel_size = '650b'
                    elif '29' in text:
                        specs.wheel_size = '29"'
                    elif '27.5' in text:
                        specs.wheel_size = '27.5"'
                
                # Gears/drivetrain
                if 'speed' in text or 'versnelling' in text:
                    import re
                    speed_match = re.search(r'(\d+)\s*(?:speed|versnelling)', text)
                    if speed_match:
                        specs.gears = f"{speed_match.group(1)} speed"
        
        return specs
    
    def extract_giant_availability(self, soup: BeautifulSoup) -> BikeAvailability:
        """Extract Giant-specific availability information"""
        availability = BikeAvailability()
        
        # Check for size selection elements
        size_elements = soup.select('.size-option, .sizes, [class*="size"], .size-guide tr')
        sizes = []
        for element in size_elements:
            size_text = element.get_text()
            # Extract common bike sizes
            import re
            size_matches = re.findall(r'\b(XS|S|M|ML|L|XL|XXL|\d{2,3}cm)\b', size_text, re.IGNORECASE)
            sizes.extend(size_matches)
        
        availability.available_sizes = list(set(sizes))
        
        # Check for color options
        color_elements = soup.select('.color-option, .colors, [class*="color"]')
        colors = []
        for element in color_elements:
            color_text = element.get_text(strip=True)
            if color_text and len(color_text) < 50:  # Reasonable color name length
                colors.append(color_text)
        
        availability.available_colors = list(set(colors))
        
        return availability
    
    def _is_bike_detail_url(self, url: str) -> bool:
        """Check if URL is a specific bike detail page (not category page)"""
        if not url:
            return False
            
        # Convert relative URLs to full URLs for pattern matching
        if url.startswith('/'):
            url = f"{self.base_url}{url}"
        
        # Patterns that indicate a specific bike detail page
        bike_detail_patterns = [
            # Specific bike model patterns like /nl/defy-advanced-eplus-elite-0-2025
            r'/nl/[a-zA-Z0-9\-]+-\d{4}$',  # ends with year
            r'/nl/[a-zA-Z0-9\-]+-[0-9]+$',  # ends with model number
            r'/nl/bikes-[a-zA-Z0-9\-]+$',   # starts with bikes-
        ]
        
        # Check if URL matches any bike detail pattern
        import re
        for pattern in bike_detail_patterns:
            if re.search(pattern, url):
                # Exclude category and listing pages
                if not any(exclude in url.lower() for exclude in [
                    '/fietsen/', 'category', 'search', 'filter', 'overview',
                    'accessories', 'accessoires', 'onderdelen', 'parts'
                ]):
                    return True
        
        return False

class CannondaleScraper(BaseBikeScraper):
    """Scraper for Cannondale bikes"""
    
    def get_bike_urls(self) -> List[str]:
        """Get all Cannondale bike URLs - focusing on individual bike detail pages"""
        urls = []
        
        try:
            # Cannondale specific category URLs for individual bikes
            category_urls = [
                f"{self.bikes_url}road",
                f"{self.bikes_url}mountain",
                f"{self.bikes_url}electric",
                f"{self.bikes_url}gravel",
                f"{self.bikes_url}urban",
                f"{self.bikes_url}kids"
            ]
            
            for category_url in category_urls:
                try:
                    logger.info(f"Searching Cannondale category: {category_url}")
                    soup = self.get_page_content(category_url)
                    
                    if soup:
                        # Look for specific bike model links in the category pages
                        potential_links = soup.find_all('a', href=True)
                        
                        for link in potential_links:
                            href = link.get('href')
                            if href and self._is_cannondale_bike_detail_url(href):
                                full_url = WebUtils.normalize_url(href, self.base_url)
                                if full_url not in urls:
                                    urls.append(full_url)
                                    logger.debug(f"Found Cannondale bike URL: {full_url}")
                                    
                        # Also look for subcategory pages that might contain individual bikes
                        subcat_links = soup.select('a[href*="/bikes/"]')
                        for sublink in subcat_links:
                            subhref = sublink.get('href')
                            if subhref and '/bikes/' in subhref and subhref != href:
                                subsoup = self.get_page_content(WebUtils.normalize_url(subhref, self.base_url))
                                if subsoup:
                                    subpotential_links = subsoup.find_all('a', href=True)
                                    for subplink in subpotential_links:
                                        subphref = subplink.get('href')
                                        if subphref and self._is_cannondale_bike_detail_url(subphref):
                                            subfull_url = WebUtils.normalize_url(subphref, self.base_url)
                                            if subfull_url not in urls:
                                                urls.append(subfull_url)
                                                logger.debug(f"Found Cannondale bike URL from subcategory: {subfull_url}")
                    
                    time.sleep(1)  # Rate limiting between categories
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape Cannondale category {category_url}: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to get Cannondale bike URLs: {str(e)}")
        
        logger.info(f"Found {len(urls)} potential Cannondale bike detail URLs")
        return urls[:50]  # Limit for testing
    
    def scrape_single_bike(self, url: str) -> Optional[Bike]:
        """Scrape a single Cannondale bike from detail page"""
        try:
            soup = self.get_page_content(url)
            if not soup:
                return None
            
            # Skip if this is a category page (similar to other scrapers)
            if any(cat in url.lower() for cat in ['category', 'search', 'overview', '/bikes/road$', '/bikes/mountain$']):
                logger.debug(f"Skipping Cannondale category page: {url}")
                return None
            
            # Extract basic information
            basic_info = self.extract_basic_info(soup, url)
            
            # Cannondale-specific model extraction - try multiple selectors
            model_name = ""
            
            # First try to extract from the main heading (most reliable)
            main_heading = soup.select_one('h1')
            if main_heading:
                heading_text = TextUtils.clean_text(main_heading.get_text())
                # Clean up common prefixes/suffixes and extract the actual model name
                if heading_text and not any(skip in heading_text.lower() for skip in ['shop', 'category', 'bikes']):
                    # Remove common marketing text and extract model
                    import re
                    # Look for patterns like "SuperSix EVO LAB71" in the heading
                    model_match = re.search(r'(SuperSix EVO[^,]*|CAAD[^,]*|Synapse[^,]*|Topstone[^,]*|Scalpel[^,]*|Jekyll[^,]*|Habit[^,]*|Trail[^,]*|Quick[^,]*|Tesoro[^,]*|Treadwell[^,]*)', heading_text, re.IGNORECASE)
                    if model_match:
                        model_name = model_match.group(1).strip()
                    else:
                        # Fallback: use the entire heading but clean it up
                        model_name = heading_text
            
            # If that didn't work, try URL-based extraction as fallback
            if not model_name:
                # Extract model from URL structure: .../supersix-evo/supersix-evo-lab71-c11135u
                url_parts = url.split('/')
                for part in reversed(url_parts):
                    if part and '-' in part and len(part) > 5:
                        # Convert URL slug to readable name
                        potential_model = part.replace('-', ' ').title()
                        # Remove model codes (like C11135U)
                        potential_model = re.sub(r'\s+[A-Z]\d+[A-Z]*\d*$', '', potential_model)
                        if potential_model and len(potential_model) > 3:
                            model_name = potential_model
                            break
            
            # Final fallback to other selectors
            if not model_name:
                fallback_selectors = [
                    '.product-title h1',
                    '.bike-title',
                    '.model-name',
                    '.product-name',
                    '[data-testid="product-name"]'
                ]
                
                for selector in fallback_selectors:
                    model_element = soup.select_one(selector)
                    if model_element:
                        model_name = TextUtils.clean_text(model_element.get_text())
                        if model_name and not any(skip in model_name.lower() for skip in ['shop', 'category', 'bikes', 'cannondale']):
                            break
            
            # Extract category from URL structure
            category = ""
            if '/road' in url:
                category = 'Road'
            elif '/mountain' in url:
                category = 'Mountain'
            elif '/electric' in url:
                category = 'Electric'
            elif '/gravel' in url:
                category = 'Gravel'
            elif '/urban' in url:
                category = 'Urban'
            elif '/kids' in url:
                category = 'Kids'
            
            basic_info['model'] = model_name
            basic_info['category'] = category
            
            # Create bike object
            bike = Bike(
                manufacturer=basic_info['manufacturer'],
                model=basic_info['model'],
                category=basic_info['category'],
                url=url
            )
            
            # Extract detailed information using enhanced methods
            bike.pricing = self.extract_cannondale_pricing(soup)
            bike.specifications = self.extract_cannondale_specifications(soup)
            bike.availability = self.extract_cannondale_availability(soup)
            bike.reviews = self.extract_reviews(soup)
            bike.images = self.extract_images(soup, bike.model)
            
            # Cannondale-specific description
            desc_selectors = ['.product-description', '.bike-description', '.overview', '.pdp-description']
            for selector in desc_selectors:
                desc_element = soup.select_one(selector)
                if desc_element:
                    bike.description = TextUtils.clean_text(desc_element.get_text())
                    break
            
            logger.info(f"Successfully scraped Cannondale bike: {bike.model}")
            return bike
            
        except Exception as e:
            logger.error(f"Failed to scrape Cannondale bike from {url}: {str(e)}")
            return None
    
    def _is_bike_url(self, url: str) -> bool:
        """Check if URL is a valid Cannondale bike product page"""
        return ('/bikes/' in url and 
                not any(exclude in url for exclude in ['category', 'search', 'filter']))
    
    def _is_cannondale_bike_detail_url(self, url: str) -> bool:
        """Check if URL is a specific Cannondale bike detail page (not category page)"""
        if not url:
            return False
            
        # Convert relative URLs to full URLs for pattern matching
        if url.startswith('/'):
            url = f"{self.base_url}{url}"
        
        # Check for essential characteristics of Cannondale bike detail pages
        import re
        
        # Cannondale bike URLs typically have specific model names and avoid category pages
        has_bikes_path = '/bikes/' in url
        
        # Check if it's NOT a category page
        not_category = not any(exclude in url.lower() for exclude in [
            'category', 'search', 'filter', 'overview',
            'accessories', 'parts'
        ])
        
        # More specific exclusions for Cannondale subcategory pages
        subcategory_patterns = [
            r'/bikes/road/?$',
            r'/bikes/mountain/?$', 
            r'/bikes/electric/?$',
            r'/bikes/gravel/?$',
            r'/bikes/urban/?$',
            r'/bikes/kids/?$',
            r'/bikes/[^/]+/race/?$',
            r'/bikes/[^/]+/endurance/?$',
            r'/bikes/[^/]+/performance/?$',
            r'/bikes/[^/]+/trail/?$',
            r'/bikes/[^/]+/cross-country/?$',
            r'/bikes/[^/]+/downhill/?$'
        ]
        
        # Check if URL matches any subcategory pattern
        is_subcategory = any(re.search(pattern, url, re.IGNORECASE) for pattern in subcategory_patterns)
        
        # Look for specific bike model patterns - Cannondale individual bikes usually have:
        # - Longer paths with specific model names
        # - Hyphenated model names
        # - Numbers or specific model identifiers
        model_indicators = [
            r'/bikes/[^/]+/[^/]+/[a-zA-Z0-9\-_]{10,}',  # Long model names
            r'/bikes/[^/]+/[^/]+/[^/]*\d+[^/]*',  # Contains numbers (model years/versions)
            r'/bikes/[^/]+/[^/]+/[^/]*-[^/]*-[^/]*',  # Multiple hyphens (detailed model names)
        ]
        
        has_model_pattern = any(re.search(pattern, url, re.IGNORECASE) for pattern in model_indicators)
        
        return (has_bikes_path and not_category and not is_subcategory and has_model_pattern)
    
    def extract_cannondale_pricing(self, soup: BeautifulSoup) -> BikePrice:
        """Extract Cannondale-specific pricing information"""
        pricing = BikePrice()
        
        # Focus specifically on the paragraph tag within the bike configuration price div
        bike_config_price_p = soup.select_one('.bike-configuration__price p')
        if bike_config_price_p:
            price_text = bike_config_price_p.get_text(strip=True)
            logger.debug(f"Cannondale price text found in <p> tag: {price_text}")
            
            # Extract price and currency from the specific paragraph element
            price, currency = TextUtils.extract_price(price_text)
            if price:
                pricing.price = price
                pricing.currency = currency if currency else 'EUR'  # Default to EUR for European site
                logger.debug(f"Cannondale pricing extracted from <p>: {pricing.price} {pricing.currency}")
                return pricing
        
        # Fallback: try the entire bike-configuration__price div
        bike_config_price = soup.select_one('.bike-configuration__price')
        if bike_config_price:
            price_text = bike_config_price.get_text(strip=True)
            logger.debug(f"Cannondale price text found in div: {price_text}")
            
            # Extract price and currency from the specific element
            price, currency = TextUtils.extract_price(price_text)
            if price:
                pricing.price = price
                pricing.currency = currency if currency else 'EUR'
                logger.debug(f"Cannondale pricing extracted from div: {pricing.price} {pricing.currency}")
                return pricing
        
        # Fallback to other Cannondale-specific price selectors
        fallback_selectors = [
            '.pdp-price',
            '.product-price',
            '.price-current',
            '[data-testid="price"]',
            '.pricing-block',
            '.bike-price',
            '.price'
        ]
        
        for selector in fallback_selectors:
            price_elements = soup.select(selector)
            for element in price_elements:
                text = element.get_text(strip=True)
                price, currency = TextUtils.extract_price(text)
                if price:
                    pricing.price = price
                    pricing.currency = currency if currency else 'EUR'
                    logger.debug(f"Cannondale fallback pricing extracted: {pricing.price} {pricing.currency}")
                    return pricing
        
        return pricing
    
    def extract_cannondale_specifications(self, soup: BeautifulSoup) -> BikeSpecification:
        """Extract Cannondale-specific specifications"""
        specs = BikeSpecification()
        
        # Look for specifications section
        spec_sections = soup.select('.specifications, .specs, .tech-specs, .product-specs, [class*="spec"]')
        
        for section in spec_sections:
            # Check for structured data in tables or lists
            spec_rows = section.select('tr, li, dt, .spec-row, .spec-item')
            
            for row in spec_rows:
                text = row.get_text().lower()
                
                # Frame material
                if 'frame' in text and 'material' in text:
                    if 'carbon' in text:
                        specs.frame_material = 'Carbon'
                    elif 'aluminum' in text or 'aluminium' in text:
                        specs.frame_material = 'Aluminum'
                    elif 'steel' in text:
                        specs.frame_material = 'Steel'
                
                # Weight
                if 'weight' in text:
                    weight = TextUtils.extract_weight(row.get_text())
                    if weight:
                        specs.weight = weight
                
                # Wheel size
                if 'wheel' in text or 'tire' in text:
                    if '700c' in text:
                        specs.wheel_size = '700c'
                    elif '650b' in text:
                        specs.wheel_size = '650b'
                    elif '29' in text:
                        specs.wheel_size = '29"'
                    elif '27.5' in text:
                        specs.wheel_size = '27.5"'
                
                # Gears/drivetrain
                if 'speed' in text or 'gear' in text:
                    import re
                    speed_match = re.search(r'(\d+)\s*(?:speed|gear)', text)
                    if speed_match:
                        specs.gears = f"{speed_match.group(1)} speed"
        
        return specs
    
    def extract_cannondale_availability(self, soup: BeautifulSoup) -> BikeAvailability:
        """Extract Cannondale-specific availability information"""
        availability = BikeAvailability()
        
        # Check for size selection elements
        size_elements = soup.select('.size-selector, .sizes, [class*="size"], .size-option')
        sizes = []
        for element in size_elements:
            size_text = element.get_text()
            # Extract common bike sizes
            import re
            size_matches = re.findall(r'\b(XS|S|M|ML|L|XL|XXL|\d{2,3}cm)\b', size_text, re.IGNORECASE)
            sizes.extend(size_matches)
        
        availability.available_sizes = list(set(sizes))
        
        # Check for color options
        color_elements = soup.select('.color-selector, .colors, [class*="color"], .color-option')
        colors = []
        for element in color_elements:
            color_text = element.get_text(strip=True)
            if color_text and len(color_text) < 50:  # Reasonable color name length
                colors.append(color_text)
        
        availability.available_colors = list(set(colors))
        
        return availability

class CanyonScraper(BaseBikeScraper):
    """Scraper for Canyon bikes"""
    
    def get_bike_urls(self) -> List[str]:
        """Get all Canyon bike URLs - focusing on individual bike detail pages"""
        urls = []
        
        try:
            # Canyon specific category URLs for individual bikes (based on actual website structure)
            category_urls = [
                f"{self.base_url}racefietsen/",
                f"{self.base_url}mountainbikes/", 
                f"{self.base_url}gravel-fietsen/",
                f"{self.base_url}elektrische-fiets/",
                f"{self.base_url}hybride-fietsen/",
                # Also try the main category pages
                f"{self.base_url}lp/fiets/",
                f"{self.base_url}lp/mountainbikes/",
                f"{self.base_url}lp/racefietsen/"
            ]
            
            for category_url in category_urls:
                try:
                    logger.info(f"Searching Canyon category: {category_url}")
                    soup = self.get_page_content(category_url)
                    
                    if soup:
                        # Look for specific bike model links
                        potential_links = soup.find_all('a', href=True)
                        
                        for link in potential_links:
                            href = link.get('href')
                            if href and self._is_canyon_bike_detail_url(href):
                                full_url = WebUtils.normalize_url(href, self.base_url)
                                if full_url not in urls:
                                    urls.append(full_url)
                                    logger.debug(f"Found Canyon bike URL: {full_url}")
                    
                    time.sleep(1)  # Rate limiting between categories
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape Canyon category {category_url}: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to get Canyon bike URLs: {str(e)}")
        
        logger.info(f"Found {len(urls)} potential Canyon bike detail URLs")
        return urls[:50]  # Limit for testing
    
    def scrape_single_bike(self, url: str) -> Optional[Bike]:
        """Scrape a single Canyon bike from detail page"""
        try:
            soup = self.get_page_content(url)
            if not soup:
                return None
            
            # Skip if this is a category page
            if any(cat in url.lower() for cat in ['category', 'search', 'overview', 'bikes/?']):
                logger.debug(f"Skipping Canyon category page: {url}")
                return None
            
            # Extract basic information
            basic_info = self.extract_basic_info(soup, url)
            
            # Canyon-specific model extraction
            model_name = ""
            
            # Try different Canyon-specific selectors for model name
            model_selectors = [
                '.productTitle__title',
                '.product-title h1',
                '.bike-title',
                '.model-name',
                'h1.title',
                'h1',
                '.product-name'
            ]
            
            for selector in model_selectors:
                model_element = soup.select_one(selector)
                if model_element:
                    model_name = TextUtils.clean_text(model_element.get_text())
                    if model_name and not any(skip in model_name.lower() for skip in ['shop', 'category', 'bikes', 'canyon']):
                        break
            
            # Extract category from URL structure
            category = ""
            if 'road' in url:
                category = 'Road'
            elif 'mountain' in url:
                category = 'Mountain'
            elif 'gravel' in url:
                category = 'Gravel'
            elif 'e-bike' in url or 'electric' in url:
                category = 'Electric'
            elif 'hybrid' in url or 'urban' in url:
                category = 'Hybrid'
            elif 'kids' in url:
                category = 'Kids'
            
            basic_info['model'] = model_name
            basic_info['category'] = category
            
            # Create bike object
            bike = Bike(
                manufacturer=basic_info['manufacturer'],
                model=basic_info['model'],
                category=basic_info['category'],
                url=url
            )
            
            # Extract detailed information using Canyon-specific methods
            bike.pricing = self.extract_canyon_pricing(soup)
            bike.specifications = self.extract_canyon_specifications(soup)
            bike.availability = self.extract_canyon_availability(soup)
            bike.reviews = self.extract_reviews(soup)
            bike.images = self.extract_images(soup, bike.model)
            
            # Canyon-specific description
            desc_selectors = ['.productDescription', '.product-description', '.bike-description', '.overview']
            for selector in desc_selectors:
                desc_element = soup.select_one(selector)
                if desc_element:
                    bike.description = TextUtils.clean_text(desc_element.get_text())
                    break
            
            logger.info(f"Successfully scraped Canyon bike: {bike.model}")
            return bike
            
        except Exception as e:
            logger.error(f"Failed to scrape Canyon bike from {url}: {str(e)}")
            return None
    
    def _is_bike_url(self, url: str) -> bool:
        """Check if URL is a valid Canyon bike product page"""
        return ('/bikes/' in url and 
                not any(exclude in url for exclude in ['category', 'search', 'filter']))
    
    def _is_canyon_bike_detail_url(self, url: str) -> bool:
        """Check if URL is a specific Canyon bike detail page (not category page)"""
        if not url:
            return False
            
        # Convert relative URLs to full URLs for pattern matching
        if url.startswith('/'):
            url = f"{self.base_url.rstrip('/')}{url}"
        
        import re
        
        # Canyon bike URLs can have various patterns:
        # /nl-nl/racefietsen/endurance-racefietsen/endurace/allroad/endurace-allroad/4164.html
        # /nl-nl/racefietsen/aero/aeroad-cf-slx-8/
        # /nl-nl/mountainbikes/trail/spectral-cf-8/
        # /nl-nl/elektrische-fiets/e-road/endurace-on-cf-8/
        
        # Must contain bike category indicators
        has_bike_category = any(cat in url.lower() for cat in [
            'racefietsen', 'mountainbikes', 'gravel-fietsen', 
            'elektrische-fiets', 'hybride-fietsen', '/bikes/'
        ])
        
        # Check if it's NOT a category page or unwanted content
        not_unwanted = not any(exclude in url.lower() for exclude in [
            'category', 'search', 'filter', 'overview',
            'accessories', 'parts', 'gear', '#section-product-grid',
            'blog-content', 'blog', 'news', 'article', 'compare',
            'size-guide', 'help', 'support', 'warranty'
        ])
        
        # Exclude bare category pages and common subcategories
        not_bare_category = not bool(re.search(r'/(racefietsen|mountainbikes|gravel-fietsen|elektrische-fiets|hybride-fietsen)/?$', url)) and \
                           not bool(re.search(r'/(endurance-racefietsen|wielrenfietsen|aero-racefietsen|triathlon-fietsen|cyclocross-fietsen|elektrische-racefiets|elektrische-gravel-fietsen|elektrische-mountainbike)/?$', url))
        
        # Must have some model/product indication
        # Be more selective - prefer deeper paths or specific model indicators
        has_model_indication = (
            # Has .html extension with number (definite product page)
            bool(re.search(r'\d{4}\.html$', url)) or
            # Has model-like naming with numbers and dashes (specific model)
            bool(re.search(r'/[a-z\-]*\d+[a-z\-]*/', url)) or
            # Has CF/AL material indicators (specific model variants)
            bool(re.search(r'/(cf|al|cfr)[-/]', url, re.IGNORECASE)) or
            # Deep path structure with model names (at least 4 segments after nl-nl)
            (len([seg for seg in url.split('/') if seg and seg != 'nl-nl']) >= 4 and
             any(model in url.lower() for model in ['endurace', 'aeroad', 'ultimate', 'grail', 'grizl', 'spectral', 'neuron', 'torque', 'grand-canyon', 'speedmax', 'inflite']))
        )
        
        # Exclude very short paths that are likely categories
        not_too_short = len([seg for seg in url.split('/') if seg and seg != 'nl-nl']) >= 3
        
        return (has_bike_category and not_unwanted and not_bare_category and has_model_indication and not_too_short)
    
    def extract_canyon_pricing(self, soup: BeautifulSoup) -> BikePrice:
        """Extract Canyon-specific pricing information"""
        pricing = BikePrice()
        
        # Focus specifically on the Canyon price sale div
        price_sale_element = soup.select_one('.productDescription__priceSale')
        if price_sale_element:
            price_text = price_sale_element.get_text(strip=True)
            logger.debug(f"Canyon price text found: {price_text}")
            
            # Extract price and currency from the specific element
            price, currency = TextUtils.extract_price(price_text)
            if price:
                pricing.price = price
                pricing.currency = currency if currency else 'EUR'
                logger.debug(f"Canyon pricing extracted: {pricing.price} {pricing.currency}")
                return pricing
        
        # Fallback to other selectors if the primary one doesn't work
        fallback_selectors = [
            '.productPrice__price',
            '.productDescription__price',
            '.price-current',
            '.product-price',
            '.price'
        ]
        
        for selector in fallback_selectors:
            price_elements = soup.select(selector)
            for element in price_elements:
                text = element.get_text(strip=True)
                price, currency = TextUtils.extract_price(text)
                if price:
                    pricing.price = price
                    pricing.currency = currency if currency else 'EUR'
                    logger.debug(f"Canyon fallback pricing extracted: {pricing.price} {pricing.currency}")
                    return pricing
        
        # Last resort - look in the entire product description container
        desc_container = soup.select_one('.productDescription')
        if desc_container:
            price_text = desc_container.get_text()
            price, currency = TextUtils.extract_price(price_text)
            if price:
                pricing.price = price
                pricing.currency = currency if currency else 'EUR'
                logger.debug(f"Canyon container pricing extracted: {pricing.price} {pricing.currency}")
        
        return pricing
    
    def extract_canyon_specifications(self, soup: BeautifulSoup) -> BikeSpecification:
        """Extract Canyon-specific specifications"""
        specs = BikeSpecification()
        
        # Look for specifications section
        spec_sections = soup.select('.specifications, .specs, .tech-specs, .product-specs, [class*="spec"]')
        
        for section in spec_sections:
            # Check for structured data in tables or lists
            spec_rows = section.select('tr, li, dt, .spec-row, .spec-item')
            
            for row in spec_rows:
                text = row.get_text().lower()
                
                # Frame material
                if 'frame' in text:
                    if 'carbon' in text or 'cf' in text:
                        specs.frame_material = 'Carbon'
                    elif 'aluminum' in text or 'aluminium' in text or 'al' in text:
                        specs.frame_material = 'Aluminum'
                    elif 'steel' in text:
                        specs.frame_material = 'Steel'
                
                # Weight
                if 'weight' in text:
                    weight = TextUtils.extract_weight(row.get_text())
                    if weight:
                        specs.weight = weight
                
                # Wheel size
                if 'wheel' in text or 'tire' in text:
                    if '700c' in text:
                        specs.wheel_size = '700c'
                    elif '650b' in text:
                        specs.wheel_size = '650b'
                    elif '29' in text:
                        specs.wheel_size = '29"'
                    elif '27.5' in text:
                        specs.wheel_size = '27.5"'
                
                # Gears/drivetrain
                if 'speed' in text or 'gear' in text:
                    import re
                    speed_match = re.search(r'(\d+)\s*(?:speed|gear)', text)
                    if speed_match:
                        specs.gears = f"{speed_match.group(1)} speed"
        
        return specs
    
    def extract_canyon_availability(self, soup: BeautifulSoup) -> BikeAvailability:
        """Extract Canyon-specific availability information"""
        availability = BikeAvailability()
        
        # Check for size selection elements
        size_elements = soup.select('.size-selector, .sizes, [class*="size"], .size-option')
        sizes = []
        for element in size_elements:
            size_text = element.get_text()
            # Extract common bike sizes
            import re
            size_matches = re.findall(r'\b(XS|S|M|ML|L|XL|XXL|\d{2,3}cm)\b', size_text, re.IGNORECASE)
            sizes.extend(size_matches)
        
        availability.available_sizes = list(set(sizes))
        
        # Check for color options
        color_elements = soup.select('.color-selector, .colors, [class*="color"], .color-option')
        colors = []
        for element in color_elements:
            color_text = element.get_text(strip=True)
            if color_text and len(color_text) < 50:  # Reasonable color name length
                colors.append(color_text)
        
        availability.available_colors = list(set(colors))
        
        return availability


# Factory function to create appropriate scraper
def create_scraper(manufacturer: str, manufacturer_config: Dict[str, Any]) -> BaseBikeScraper:
    """Factory function to create appropriate scraper for manufacturer"""
    scrapers = {
        'trek': TrekScraper,
        'specialized': SpecializedScraper,
        'giant': GiantScraper,
        'cannondale': CannondaleScraper,
        'canyon': CanyonScraper
    }
    
    scraper_class = scrapers.get(manufacturer.lower())
    if scraper_class:
        return scraper_class(manufacturer_config)
    else:
        raise ValueError(f"No scraper available for manufacturer: {manufacturer}")
