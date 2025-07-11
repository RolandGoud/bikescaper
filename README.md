# Trek Bikes Scraper

A comprehensive web scraper for Trek road bikes from the Dutch Trek website (trekbikes.com/nl). This scraper extracts detailed bike specifications, descriptions, and pricing information with intelligent predictions for missing data.

## Features

- **Complete bike data extraction** from Trek's Dutch website
- **Detailed specifications** extracted from individual bike pages
- **Intelligent predictions** for missing fields (framefit, bottom bracket, chain)
- **Transparent predictions** marked with asterisk (*) for clarity
- **Color variant detection** for bikes with multiple color options
- **1x drivetrain detection** with automatic front derailleur classification
- **Multiple export formats**: JSON, CSV, and Excel
- **Comprehensive logging** for debugging and monitoring
- **Automatic file cleanup** to manage storage

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd bikescaper
```

2. Install required dependencies:
```bash
pip3 install -r requirements.txt
```

## Usage

Run the scraper:
```bash
python3 trek_bikes_scraper.py
```

The scraper will:
1. Extract all road bikes from Trek's Dutch website
2. Fetch detailed specifications for each bike
3. Apply intelligent predictions for missing data
4. Export data to multiple formats in the `data/` directory

## Output Files

The scraper generates timestamped files and maintains latest versions:

- `trek_bikes_YYYYMMDD_HHMMSS.json` - Complete data in JSON format
- `trek_bikes_YYYYMMDD_HHMMSS.csv` - Tabular data for analysis
- `trek_bikes_YYYYMMDD_HHMMSS.xlsx` - Excel format for easy viewing
- `trek_bikes_latest.*` - Always contains the most recent data

## Data Fields

### Basic Information
- `name` - Bike model name
- `price` - Price in euros
- `category` - Bike category (e.g., "Performance road bikes")
- `brand` - Always "Trek"
- `url` - Relative URL to bike detail page
- `sku` - Product SKU
- `variant` - Color variant name
- `description` - Marketing description

### Specifications
All specifications are prefixed with `spec_` in CSV/Excel formats:

- **Framefit*** - Riding position (Endurance, H1.5 Race, Comfort, Triatlon)
- **Bottom bracket*** - Bottom bracket type and threading
- **Ketting (Chain)*** - Chain specifications
- **Voorvork** - Fork specifications
- **Voorderailleur** - Front derailleur (or "geen voor-derailleur" for 1x)
- **Achterderailleur** - Rear derailleur
- **Cassette** - Cassette specifications
- **Voortandwiel** - Chainring specifications
- And many more technical specifications...

*Fields marked with asterisk (*) indicate intelligent predictions based on component compatibility.

## Intelligent Predictions

The scraper includes sophisticated prediction algorithms:

### Framefit Prediction
- **Endurance**: Domane, Checkpoint series
- **H1.5 Race**: Madone, Émonda, Boone series
- **Comfort**: FX fitness bikes
- **Triatlon**: Speed Concept series

### Bottom Bracket Prediction
- **SRAM DUB**: High-end bikes with AXS components
- **SRAM DUB Wide**: Gravel bikes (Checkpoint series)
- **Praxis T47**: Most carbon Trek bikes
- **Shimano**: Entry-level and fitness bikes

### Chain Prediction
Based on drivetrain components:
- **SRAM chains**: Matched to Apex, Rival, Force, RED components
- **Shimano chains**: Matched to 105, Ultegra, XT components
- **Speed-specific**: 10, 11, 12, or 13-speed chains

### 1x Drivetrain Detection
Automatically detects single-chainring setups and adds "geen voor-derailleur" based on:
- Chainring specifications
- Wide-range cassettes (>30 tooth range)
- Component naming patterns

## Logging

The scraper maintains detailed logs in `trek_scraper.log` including:
- Extraction progress
- Specification counts
- Prediction reasoning
- Error handling
- Performance metrics

## Error Handling

- **Robust request handling** with retries and timeouts
- **Graceful failure** for individual bikes
- **Comprehensive logging** for debugging
- **Data validation** to ensure quality

## Data Quality

- **100% field coverage** - No missing critical specifications
- **Transparent predictions** - All predictions clearly marked with *
- **Duplicate removal** - Ensures unique bike models
- **Data validation** - Specifications verified against patterns

## Recent Updates

- ✅ Added asterisk markers for all predicted fields
- ✅ Improved chain specification extraction
- ✅ Enhanced 1x drivetrain detection
- ✅ Better bottom bracket prediction
- ✅ Comprehensive framefit determination

## Requirements

- Python 3.7+
- Internet connection
- Dependencies listed in requirements.txt

## License

This project is for educational and research purposes. Please respect Trek's website terms of service and use responsibly. 