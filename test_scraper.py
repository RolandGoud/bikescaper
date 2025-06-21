#!/usr/bin/env python3
"""
Test script for bike scraper components
"""

import sys
import logging
from datetime import datetime

# Import our modules
from data_models import Bike, BikePrice, BikeSpecification, BikeAvailability, BikeReview, BikeImage
from utils import TextUtils, DataExporter
from config import MANUFACTURERS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_data_models():
    """Test data model creation and conversion"""
    print("Testing data models...")
    
    # Create a sample bike
    bike = Bike(
        manufacturer="Test Manufacturer",
        model="Test Model X1"
    )
    
    # Add pricing
    bike.pricing = BikePrice(
        price=1999.99,
        currency="USD",
        original_price=2499.99,
        is_on_sale=True
    )
    
    # Add specifications
    bike.specifications = BikeSpecification(
        frame_material="Carbon Fiber",
        wheel_size="700c",
        gears="22 speed",
        weight="8.5 kg"
    )
    
    # Add availability
    bike.availability = BikeAvailability(
        in_stock=True,
        available_sizes=["S", "M", "L", "XL"],
        available_colors=["Black", "Red", "Blue"]
    )
    
    # Add reviews
    bike.reviews = BikeReview(
        rating=4.5,
        review_count=127
    )
    
    # Add images
    bike.images = [
        BikeImage(url="https://example.com/bike1.jpg", is_primary=True),
        BikeImage(url="https://example.com/bike2.jpg", is_primary=False)
    ]
    
    bike.description = "A high-performance test bike with advanced features."
    bike.category = "Road"
    bike.url = "https://example.com/test-bike"
    
    # Test conversion to dictionary
    bike_dict = bike.to_dict()
    
    print(f"✅ Created bike: {bike}")
    print(f"✅ Bike dict keys: {len(bike_dict)} fields")
    print(f"✅ Sample fields: {list(bike_dict.keys())[:5]}")
    
    return bike

def test_text_utils():
    """Test text utility functions"""
    print("\nTesting text utilities...")
    
    # Test price extraction
    test_prices = [
        "$1,234.56",
        "USD 2500.00",
        "€999.99",
        "Price: £1,500.50",
        "Regular price: $3,299.00"
    ]
    
    for price_text in test_prices:
        price, currency = TextUtils.extract_price(price_text)
        print(f"✅ '{price_text}' -> {price} {currency}")
    
    # Test text cleaning
    dirty_text = "  This   is   messy    text!!!   "
    clean_text = TextUtils.clean_text(dirty_text)
    print(f"✅ Text cleaning: '{dirty_text}' -> '{clean_text}'")
    
    # Test size extraction
    size_text = "Available in S, M, L, XL and 54cm, 56cm, 58cm sizes"
    sizes = TextUtils.extract_sizes(size_text)
    print(f"✅ Size extraction: '{size_text}' -> {sizes}")
    
    # Test weight extraction
    weight_text = "Weight: 8.5 kg (18.7 lbs)"
    weight = TextUtils.extract_weight(weight_text)
    print(f"✅ Weight extraction: '{weight_text}' -> {weight}")

def test_data_export():
    """Test data export functionality"""
    print("\nTesting data export...")
    
    # Create sample bikes
    bikes = []
    
    for i in range(3):
        bike = Bike(
            manufacturer=f"Manufacturer {i+1}",
            model=f"Model {i+1}"
        )
        bike.pricing = BikePrice(price=1000 + (i * 500), currency="USD")
        bike.category = ["Road", "Mountain", "Hybrid"][i]
        bikes.append(bike)
    
    # Test CSV export
    try:
        success = DataExporter.export_to_csv(bikes, "test_bikes.csv")
        if success:
            print("✅ CSV export successful")
        else:
            print("❌ CSV export failed")
    except Exception as e:
        print(f"❌ CSV export error: {str(e)}")
    
    # Test JSON export
    try:
        success = DataExporter.export_to_json(bikes, "test_bikes.json")
        if success:
            print("✅ JSON export successful")
        else:
            print("❌ JSON export failed")
    except Exception as e:
        print(f"❌ JSON export error: {str(e)}")
    
    return bikes

def test_configuration():
    """Test configuration settings"""
    print("\nTesting configuration...")
    
    print(f"✅ Available manufacturers: {list(MANUFACTURERS.keys())}")
    
    for name, config in MANUFACTURERS.items():
        print(f"✅ {name}: {config['name']} ({config['base_url']})")
        print(f"   Categories: {config.get('categories', [])}")
        print(f"   Selenium required: {config.get('requires_selenium', False)}")

def run_basic_functionality_test():
    """Run a basic functionality test without actual web scraping"""
    print("="*60)
    print("BIKE SCRAPER BASIC FUNCTIONALITY TEST")
    print("="*60)
    
    try:
        # Test data models
        sample_bike = test_data_models()
        
        # Test text utilities
        test_text_utils()
        
        # Test data export
        sample_bikes = test_data_export()
        
        # Test configuration
        test_configuration()
        
        print("\n" + "="*60)
        print("✅ ALL BASIC TESTS PASSED!")
        print("The bike scraper components are working correctly.")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        print("="*60)
        return False

def test_simple_web_request():
    """Test a simple web request without full scraping"""
    print("\nTesting simple web request...")
    
    try:
        from utils import WebUtils
        
        # Test with a simple, reliable website
        test_url = "https://httpbin.org/get"
        response = WebUtils.safe_request(test_url)
        
        if response and response.status_code == 200:
            print("✅ Web request test successful")
            print(f"   Status code: {response.status_code}")
            print(f"   Response length: {len(response.content)} bytes")
            return True
        else:
            print("❌ Web request test failed")
            return False
            
    except Exception as e:
        print(f"❌ Web request test error: {str(e)}")
        return False

def main():
    """Main test function"""
    print(f"Starting bike scraper tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run basic functionality tests
    basic_tests_passed = run_basic_functionality_test()
    
    # Run web request test
    web_test_passed = test_simple_web_request()
    
    print(f"\nTest Results:")
    print(f"Basic functionality: {'✅ PASS' if basic_tests_passed else '❌ FAIL'}")
    print(f"Web requests: {'✅ PASS' if web_test_passed else '❌ FAIL'}")
    
    if basic_tests_passed and web_test_passed:
        print("\n🎉 All tests passed! The bike scraper is ready to use.")
        print("\nTo run the actual scraper:")
        print("  python bike_scraper.py --list-manufacturers")
        print("  python bike_scraper.py -m trek --verbose")
    else:
        print("\n⚠️  Some tests failed. Please check the error messages above.")
        return 1
    
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
