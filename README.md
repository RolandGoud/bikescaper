# Bike Scraper

A comprehensive web scraper for collecting detailed bike information from major manufacturer websites including Trek, Specialized, Giant, and Cannondale.

## Features

- **Multi-manufacturer support**: Scrape from Trek, Specialized, Giant, and Cannondale
- **Comprehensive data extraction**: Model, price, specifications, availability, reviews, images
- **Multiple output formats**: CSV, JSON, Excel
- **Robust scraping**: Handles both standard HTTP requests and JavaScript-heavy sites using Selenium
- **Rate limiting**: Built-in delays to be respectful to websites
- **Error handling**: Graceful handling of failed requests and missing data
- **Configurable**: Easy to add new manufacturers or modify scraping parameters
- **Command-line interface**: Easy to use from terminal

## Installation

1. **Clone or download the project**
2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Chrome browser** (required for Selenium-based scrapers)

## Usage

### Basic Usage

Scrape all manufacturers and export to CSV and JSON:
```bash
python bike_scraper.py
```

### Scrape Specific Manufacturers

Scrape only Trek bikes:
```bash
python bike_scraper.py -m trek
```

Scrape Trek and Specialized:
```bash
python bike_scraper.py -m trek specialized
```

### Output Options

Export to different formats:
```bash
python bike_scraper.py -f csv json excel
```

Specify custom output directory:
```bash
python bike_scraper.py -o my_bike_data
```

### Advanced Options

Enable verbose logging:
```bash
python bike_scraper.py -v
```

List available manufacturers:
```bash
python bike_scraper.py --list-manufacturers
```

## Data Fields Collected

For each bike, the scraper attempts to collect:

### Basic Information
- Manufacturer
- Model name
- Category (Road, Mountain, Hybrid, Electric, etc.)
- Year
- SKU/Product code

### Pricing
- Current price
- Original price (if on sale)
- Currency
- Sale status

### Specifications
- Frame material
- Frame sizes available
- Wheel size
- Tire size
- Number of gears
- Drivetrain components
- Brake type
- Suspension type
- Weight
- Maximum weight capacity

### Availability
- Stock status
- Available sizes
- Available colors
- Estimated delivery time

### Reviews
- Average rating
- Number of reviews
- Review summary

### Images
- Product images
- Image descriptions
- Primary image identification

### Additional
- Product description
- Key features
- Product URL
- Scraping timestamp

## Output Files

The scraper generates the following files in the output directory (default: `data/`):

- **bikes_data.csv**: Complete dataset in CSV format
- **bikes_data.json**: Complete dataset in JSON format
- **bikes_data.xlsx**: Complete dataset in Excel format (if requested)
- **bike_scraper.log**: Log file with scraping details

## Project Structure

```
bike_scraper/
├── bike_scraper.py      # Main application entry point
├── base_scraper.py      # Base scraper class with common functionality
├── manufacturers.py     # Manufacturer-specific scraper implementations
├── data_models.py       # Data models for bike information
├── utils.py            # Utility functions for text processing, exports, etc.
├── config.py           # Configuration settings and manufacturer URLs
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Supported Manufacturers

| Manufacturer | Website | Status | Selenium Required |
|-------------|---------|--------|------------------|
| Trek | trekbikes.com | ✅ Active | Yes |
| Specialized | specialized.com | ✅ Active | Yes |
| Giant | giant-bicycles.com | ✅ Active | No |
| Cannondale | cannondale.com | ✅ Active | Yes |

## Configuration

### Adding New Manufacturers

To add a new manufacturer, edit `config.py` and add an entry to the `MANUFACTURERS` dictionary:

```python
"new_manufacturer": {
    "name": "New Manufacturer",
    "base_url": "https://www.newmanufacturer.com",
    "bikes_url": "https://www.newmanufacturer.com/bikes",
    "categories": ["road", "mountain", "electric"],
    "requires_selenium": False
}
```

Then create a corresponding scraper class in `manufacturers.py`.

### Modifying Scraping Parameters

Edit the `ScrapingConfig` class in `config.py` to adjust:
- Request delays
- Timeout values
- Retry attempts
- User agent strings

## Rate Limiting and Ethics

This scraper is designed to be respectful to websites:
- Built-in delays between requests (default: 1 second)
- Reasonable timeout values
- Proper error handling to avoid overwhelming servers
- User-agent rotation

**Please use responsibly and check robots.txt files before scraping.**

## Troubleshooting

### Common Issues

**ChromeDriver not found**:
- Make sure Chrome browser is installed
- The webdriver-manager package should automatically download ChromeDriver

**No bikes found**:
- Websites may have changed their structure
- Check the log file for specific error messages
- Some sites may block automated access

**Memory issues**:
- Reduce the number of bikes scraped per manufacturer
- Close other applications to free up memory

### Debug Mode

Run with verbose logging to see detailed information:
```bash
python bike_scraper.py -v
```

Check the log file `bike_scraper.log` for detailed error messages.

## Example Output

### Console Output
```
============================================================
BIKE SCRAPING SUMMARY
============================================================
Total bikes scraped: 127

By Manufacturer:
  Trek: 45 bikes
  Specialized: 38 bikes
  Giant: 44 bikes

By Category:
  Road: 52 bikes
  Mountain: 41 bikes
  Electric: 23 bikes
  Hybrid: 11 bikes

Price Statistics:
  Average price: $2,847.50
  Min price: $599.00
  Max price: $12,999.00
  Bikes with pricing: 115/127

Scraping completed at: 2024-01-15 14:30:22
============================================================
```

### CSV Output Sample
```csv
manufacturer,model,category,price,currency,frame_material,wheel_size,gears,weight,url
Trek,Domane AL 2,Road,1199.99,USD,Aluminum,700c,16 speed,10.5 kg,https://www.trekbikes.com/...
Specialized,Tarmac SL7,Road,3200.00,USD,Carbon,700c,22 speed,8.2 kg,https://www.specialized.com/...
```

## License

This project is for educational purposes. Please respect the terms of service of the websites you scrape and use the data responsibly.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Test thoroughly
5. Submit a pull request

When adding new manufacturers:
1. Add configuration to `config.py`
2. Create scraper class in `manufacturers.py`
3. Test with a small sample first
4. Update documentation
