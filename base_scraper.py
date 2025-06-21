# Base scraper class for bike manufacturers
from abc import ABC, abstractmethod
import time
import logging
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent
from tqdm import tqdm

from data_models import Bike, BikePrice, BikeSpecification, BikeAvailability, BikeReview, BikeImage
from utils import TextUtils, WebUtils, ImageUtils
from config import ScrapingConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

class BaseBikeScraper(ABC):
    """Abstract base class for bike manufacturer scrapers"""
    
    def __init__(self, manufacturer_config: Dict[str, Any], scraping_config: ScrapingConfig = DEFAULT_CONFIG):
        self.manufacturer_config = manufacturer_config
        self.scraping_config = scraping_config
        self.manufacturer_name = manufacturer_config.get('name', 'Unknown')
        self.base_url = manufacturer_config.get('base_url', '')
        self.bikes_url = manufacturer_config.get('bikes_url', '')
        self.requires_selenium = manufacturer_config.get('requires_selenium', False)
        
        self.session = requests.Session()
        self.driver = None
        self.scraped_bikes: List[Bike] = []
        
        # Set up session headers
        self.session.headers.update({
            'User-Agent': WebUtils.get_random_user_agent()
        })
    
    def __enter__(self):
        """Context manager entry"""
        if self.requires_selenium:
            self._setup_selenium()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.driver:
            self.driver.quit()
    
    def _setup_selenium(self):
        """Set up Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={WebUtils.get_random_user_agent()}')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info(f"Selenium WebDriver set up for {self.manufacturer_name}")
            
        except Exception as e:
            logger.error(f"Failed to set up Selenium: {str(e)}")
            raise
    
    def get_page_content(self, url: str, use_selenium: bool = None) -> Optional[BeautifulSoup]:
        """Get page content using requests or Selenium"""
        use_selenium = use_selenium if use_selenium is not None else self.requires_selenium
        
        try:
            if use_selenium and self.driver:
                self.driver.get(url)
                time.sleep(self.scraping_config.delay_between_requests)
                
                # Wait for page to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except TimeoutException:
                    logger.warning(f"Page load timeout for {url}")
                
                html_content = self.driver.page_source
                return BeautifulSoup(html_content, 'html.parser')
            
            else:
                response = WebUtils.safe_request(url, timeout=self.scraping_config.timeout)
                if response:
                    return BeautifulSoup(response.content, 'html.parser')
                
        except Exception as e:
            logger.error(f"Failed to get page content for {url}: {str(e)}")
        
        return None
    
    def scrape_all_bikes(self) -> List[Bike]:
        """Main method to scrape all bikes from manufacturer"""
        logger.info(f"Starting to scrape bikes from {self.manufacturer_name}")
        
        try:
            # Get all bike URLs
            bike_urls = self.get_bike_urls()
            logger.info(f"Found {len(bike_urls)} bike URLs")
            
            if not bike_urls:
                logger.warning("No bike URLs found")
                return []
            
            # Scrape each bike
            for url in tqdm(bike_urls, desc=f"Scraping {self.manufacturer_name} bikes"):
                try:
                    bike = self.scrape_single_bike(url)
                    if bike:
                        self.scraped_bikes.append(bike)
                    
                    # Rate limiting
                    time.sleep(self.scraping_config.delay_between_requests)
                    
                except Exception as e:
                    logger.error(f"Failed to scrape bike from {url}: {str(e)}")
                    continue
            
            logger.info(f"Successfully scraped {len(self.scraped_bikes)} bikes from {self.manufacturer_name}")
            return self.scraped_bikes
            
        except Exception as e:
            logger.error(f"Failed to scrape bikes from {self.manufacturer_name}: {str(e)}")
            return []
    
    @abstractmethod
    def get_bike_urls(self) -> List[str]:
        """Get all bike URLs for the manufacturer"""
        pass
    
    @abstractmethod
    def scrape_single_bike(self, url: str) -> Optional[Bike]:
        """Scrape a single bike from its URL"""
        pass
    
    def extract_basic_info(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract basic bike information - to be overridden by subclasses"""
        return {
            'manufacturer': self.manufacturer_name,
            'model': '',
            'category': '',
            'url': url
        }
    
    def extract_pricing(self, soup: BeautifulSoup) -> BikePrice:
        """Extract pricing information"""
        price_selectors = [
            '.price', '.product-price', '[class*="price"]',
            '.cost', '.product-cost', '[data-price]'
        ]
        
        for selector in price_selectors:
            price_elements = soup.select(selector)
            for element in price_elements:
                text = element.get_text(strip=True)
                price, currency = TextUtils.extract_price(text)
                if price:
                    # Check for original price (sale scenarios)
                    original_price = None
                    parent = element.parent
                    if parent:
                        original_text = parent.get_text()
                        if 'was' in original_text.lower() or 'originally' in original_text.lower():
                            # Look for crossed out or different styled price
                            pass  # Implementation for finding original price
                    
                    return BikePrice(
                        price=price,
                        currency=currency,
                        original_price=original_price,
                        is_on_sale=original_price is not None
                    )
        
        return BikePrice()
    
    def extract_specifications(self, soup: BeautifulSoup) -> BikeSpecification:
        """Extract bike specifications"""
        specs = BikeSpecification()
        
        # Common specification selectors
        spec_sections = soup.select('.specifications, .specs, .tech-specs, [class*="spec"]')
        
        for section in spec_sections:
            text = section.get_text().lower()
            
            # Frame material
            if 'frame' in text and any(material in text for material in ['aluminum', 'carbon', 'steel', 'titanium']):
                for material in ['carbon fiber', 'carbon', 'aluminum', 'steel', 'titanium']:
                    if material in text:
                        specs.frame_material = material.title()
                        break
            
            # Weight
            weight = TextUtils.extract_weight(text)
            if weight:
                specs.weight = weight
            
            # Gears/drivetrain
            if any(term in text for term in ['speed', 'gear', 'drivetrain']):
                import re
                gear_match = re.search(r'(\d+)\s*speed', text)
                if gear_match:
                    specs.gears = f"{gear_match.group(1)} speed"
        
        return specs
    
    def extract_availability(self, soup: BeautifulSoup) -> BikeAvailability:
        """Extract availability information"""
        availability = BikeAvailability()
        
        # Check stock status
        stock_indicators = soup.select('.in-stock, .out-of-stock, .stock-status, [class*="stock"]')
        for indicator in stock_indicators:
            text = indicator.get_text().lower()
            if 'in stock' in text or 'available' in text:
                availability.in_stock = True
            elif 'out of stock' in text or 'unavailable' in text:
                availability.in_stock = False
        
        # Extract sizes
        size_elements = soup.select('.size-option, .sizes, [class*="size"]')
        sizes = []
        for element in size_elements:
            text = element.get_text()
            extracted_sizes = TextUtils.extract_sizes(text)
            sizes.extend(extracted_sizes)
        availability.available_sizes = list(set(sizes))
        
        # Extract colors
        color_elements = soup.select('.color-option, .colors, [class*="color"]')
        colors = []
        for element in color_elements:
            color = element.get('title') or element.get('data-color') or element.get_text(strip=True)
            if color and len(color) < 50:  # Reasonable color name length
                colors.append(color)
        availability.available_colors = list(set(colors))
        
        return availability
    
    def extract_reviews(self, soup: BeautifulSoup) -> BikeReview:
        """Extract review information"""
        reviews = BikeReview()
        
        # Rating
        rating_selectors = ['.rating', '.stars', '[class*="rating"]', '[data-rating]']
        for selector in rating_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Try to extract numeric rating
                rating_text = element.get_text() or element.get('data-rating', '')
                import re
                rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                if rating_match:
                    try:
                        rating = float(rating_match.group(1))
                        if 0 <= rating <= 5:  # Assuming 5-star rating system
                            reviews.rating = rating
                            break
                    except ValueError:
                        continue
        
        # Review count
        review_count_selectors = ['.review-count', '.reviews-count', '[class*="review"]']
        for selector in review_count_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                import re
                count_match = re.search(r'(\d+)', text)
                if count_match:
                    try:
                        reviews.review_count = int(count_match.group(1))
                        break
                    except ValueError:
                        continue
        
        return reviews
    
    def extract_images(self, soup: BeautifulSoup, bike_model: str) -> List[BikeImage]:
        """Extract bike images"""
        images = []
        
        # Common image selectors
        img_selectors = [
            '.product-image img', '.bike-image img', '.gallery img',
            '.hero-image img', '[class*="image"] img'
        ]
        
        for selector in img_selectors:
            img_elements = soup.select(selector)
            for i, img in enumerate(img_elements):
                src = img.get('src') or img.get('data-src')
                if src:
                    # Normalize URL
                    src = WebUtils.normalize_url(src, self.base_url)
                    
                    # Skip very small images (likely icons)
                    if any(size in src for size in ['16x16', '32x32', 'icon', 'favicon']):
                        continue
                    
                    bike_image = BikeImage(
                        url=src,
                        alt_text=img.get('alt', ''),
                        is_primary=(i == 0)
                    )
                    images.append(bike_image)
        
        # Remove duplicates while preserving order
        seen_urls = set()
        unique_images = []
        for img in images:
            if img.url not in seen_urls:
                seen_urls.add(img.url)
                unique_images.append(img)
        
        return unique_images[:10]  # Limit to 10 images per bike
