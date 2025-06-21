# Utility functions for bike scraper
import re
import os
import json
import csv
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import time
import logging
from data_models import Bike

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TextUtils:
    """Utility functions for text processing"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        return text
    
    @staticmethod
    def extract_price(text: str) -> tuple[Optional[float], str]:
        """Extract price from text"""
        if not text:
            return None, "USD"
        
        # Common price patterns - handle both US and European formatting
        patterns = [
            # US format (comma thousands separator, period decimal)
            r'\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',  # $1,234.56
            r'USD\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',  # USD 1234.56
            r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*USD',  # 1234.56 USD
            
            # European format with Euro (period thousands separator, comma decimal)
            r'€\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})?)',  # €1.234,56
            r'([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})?)\s*€',  # 1.234,56 €
            
            # US format with Euro (comma thousands separator, period decimal) 
            r'€\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',  # €1,234.56
            r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*EUR',  # 1234.56 EUR
            
            # British Pounds
            r'£\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',  # £1,234.56
            r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*GBP',  # 1234.56 GBP
            
            # Simple number patterns without currency symbols
            r'([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})?)',  # European: 1.234,56
            r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',  # US: 1,234.56
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1)
                
                try:
                    # Determine if this is European or US formatting
                    if '€' in text:
                        currency = 'EUR'
                        # Handle European formatting (period as thousands, comma as decimal)
                        if ',' in price_str and price_str.count('.') > 0:
                            # European format: 1.234,56
                            price_str = price_str.replace('.', '').replace(',', '.')
                        elif '.' in price_str and ',' not in price_str:
                            # Could be thousands separator: 1.234 -> 1234
                            if len(price_str.split('.')[-1]) == 3:
                                price_str = price_str.replace('.', '')
                    elif '$' in text or 'USD' in text:
                        currency = 'USD'
                        # US formatting (comma as thousands, period as decimal)
                        price_str = price_str.replace(',', '')
                    elif '£' in text or 'GBP' in text:
                        currency = 'GBP'
                        price_str = price_str.replace(',', '')
                    else:
                        # Default currency determination based on formatting
                        if ',' in price_str and price_str.count('.') > 0:
                            # Likely European format
                            currency = 'EUR'
                            price_str = price_str.replace('.', '').replace(',', '.')
                        else:
                            currency = 'USD'
                            price_str = price_str.replace(',', '')
                    
                    price = float(price_str)
                    return price, currency
                    
                except ValueError:
                    continue
        
        return None, "USD"
    
    @staticmethod
    def extract_weight(text: str) -> Optional[str]:
        """Extract weight from text"""
        if not text:
            return None
        
        # Weight patterns
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(kg|kilograms)',
            r'(\d+(?:\.\d+)?)\s*(lbs?|pounds)',
            r'(\d+(?:\.\d+)?)\s*(g|grams)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} {match.group(2).lower()}"
        
        return None
    
    @staticmethod
    def extract_sizes(text: str) -> List[str]:
        """Extract available sizes from text"""
        if not text:
            return []
        
        # Common bike size patterns
        size_patterns = [
            r'\b(XS|S|M|L|XL|XXL)\b',
            r'\b(\d{2,3})\s*cm\b',
            r'\b(\d{1,2})\s*inch\b',
            r'\b(\d{1,2}\.?\d?)\s*"\b',
        ]
        
        sizes = []
        for pattern in size_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            sizes.extend(matches)
        
        return list(set(sizes))  # Remove duplicates

class ImageUtils:
    """Utility functions for image handling"""
    
    @staticmethod
    def download_image(url: str, filename: str, directory: str = "images") -> bool:
        """Download image from URL"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            # Get user agent
            ua = UserAgent()
            headers = {'User-Agent': ua.random}
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            filepath = os.path.join(directory, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded image: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download image {url}: {str(e)}")
            return False
    
    @staticmethod
    def get_image_filename(url: str, bike_model: str, index: int = 0) -> str:
        """Generate filename for image"""
        # Get file extension
        parsed_url = urlparse(url)
        path = parsed_url.path
        ext = os.path.splitext(path)[1] or '.jpg'
        
        # Clean bike model name
        clean_model = re.sub(r'[^\w\s-]', '', bike_model)
        clean_model = re.sub(r'\s+', '_', clean_model.strip())
        
        return f"{clean_model}_{index}{ext}"

class DataExporter:
    """Utility functions for data export"""
    
    @staticmethod
    def export_to_csv(bikes: List[Bike], filename: str) -> bool:
        """Export bikes data to CSV"""
        try:
            if not bikes:
                logger.warning("No bikes data to export")
                return False
            
            # Convert bikes to dictionaries
            bike_dicts = [bike.to_dict() for bike in bikes]
            
            # Create DataFrame
            df = pd.DataFrame(bike_dicts)
            
            # Export to CSV
            df.to_csv(filename, index=False)
            logger.info(f"Exported {len(bikes)} bikes to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export to CSV: {str(e)}")
            return False
    
    @staticmethod
    def export_to_json(bikes: List[Bike], filename: str) -> bool:
        """Export bikes data to JSON"""
        try:
            if not bikes:
                logger.warning("No bikes data to export")
                return False
            
            # Convert bikes to dictionaries
            bike_dicts = [bike.to_dict() for bike in bikes]
            
            # Export to JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(bike_dicts, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Exported {len(bikes)} bikes to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export to JSON: {str(e)}")
            return False
    
    @staticmethod
    def export_to_excel(bikes: List[Bike], filename: str) -> bool:
        """Export bikes data to Excel"""
        try:
            if not bikes:
                logger.warning("No bikes data to export")
                return False
            
            # Convert bikes to dictionaries
            bike_dicts = [bike.to_dict() for bike in bikes]
            
            # Create DataFrame
            df = pd.DataFrame(bike_dicts)
            
            # Export to Excel
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Bikes', index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets['Bikes']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"Exported {len(bikes)} bikes to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export to Excel: {str(e)}")
            return False

class WebUtils:
    """Utility functions for web scraping"""
    
    @staticmethod
    def get_random_user_agent() -> str:
        """Get random user agent"""
        try:
            ua = UserAgent()
            return ua.random
        except:
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    @staticmethod
    def safe_request(url: str, headers: Dict[str, str] = None, timeout: int = 30) -> Optional[requests.Response]:
        """Make a safe HTTP request with retries"""
        if not headers:
            headers = {'User-Agent': WebUtils.get_random_user_agent()}
        
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                return response
            except Exception as e:
                logger.warning(f"Request attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt < 2:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"All request attempts failed for {url}")
        return None
    
    @staticmethod
    def normalize_url(url: str, base_url: str) -> str:
        """Normalize URL by joining with base URL if needed"""
        if url.startswith('http'):
            return url
        return urljoin(base_url, url)
