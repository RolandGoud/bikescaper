# Bike Scraper Suite

A comprehensive bike scraping system with **automatic WordPress integration** and **organized file management**.

## 🚀 **Available Scrapers**

### 1. 🚲 **Trek Bikes Scraper** (`trek_bikes_scraper.py`)
- **Source**: Trek Dutch website (complete road bikes catalog)
- **Data**: 60+ bike models with full specifications
- **Status**: ✅ **Production Ready** - Fully tested and optimized

### 2. 🏔️ **Canyon Bikes Scraper** (`canyon_bikes_scraper.py`) - NEW!
- **Source**: Canyon Dutch website (road bikes catalog)
- **Data**: Road bikes across all series (Endurace, Ultimate, Aeroad, etc.)
- **Status**: 🧪 **Beta** - Core functionality working, fine-tuning in progress

## 📁 **Organized File Structure**

Both scrapers automatically organize output files by brand:

```
data/
├── trek_bikes_latest.*              # Trek current data
├── canyon_bikes_latest.*            # Canyon current data (NEW!)
├── Trek/                           # Trek timestamped exports
│   ├── trek_bikes_YYYYMMDD_HHMMSS.json
│   ├── trek_bikes_YYYYMMDD_HHMMSS.csv
│   └── trek_bikes_YYYYMMDD_HHMMSS.xlsx
├── Canyon/                         # Canyon timestamped exports (NEW!)
│   ├── canyon_bikes_YYYYMMDD_HHMMSS.json
│   ├── canyon_bikes_YYYYMMDD_HHMMSS.csv
│   └── canyon_bikes_YYYYMMDD_HHMMSS.xlsx
├── wordpress_imports/              # WordPress-ready files
│   ├── trek_bikes_wordpress_*.csv
│   └── canyon_bikes_wordpress_*.csv (NEW!)
├── archive/                        # Historical data preservation
│   ├── Trek/                       # Archived Trek exports
│   ├── Canyon/                     # Archived Canyon exports (NEW!)
│   └── wordpress_imports/          # Archived WordPress files
└── images/
    ├── Trek/                       # Trek bike images
    └── Canyon/                     # Canyon bike images (NEW!)
```

## ⚡ **Quick Start**

### Trek Bikes (Production Ready)
```bash
python3 trek_bikes_scraper.py
```
✅ **Automatically creates**:
- Brand exports in `data/Trek/`
- WordPress CSV in `data/wordpress_imports/`
- Downloaded images in `images/Trek/`
- Archives old files automatically

### Canyon Bikes (Beta)
```bash
python3 canyon_bikes_scraper.py
```
✅ **Automatically creates**:
- Brand exports in `data/Canyon/`
- WordPress CSV in `data/wordpress_imports/`
- Downloaded images in `images/Canyon/`
- Archives old files automatically

## 🔄 **WordPress Integration**

Both scrapers include **automatic WordPress conversion**:

- **Trek files**: `trek_bikes_wordpress_YYYYMMDD_HHMMSS.csv`
- **Canyon files**: `canyon_bikes_wordpress_YYYYMMDD_HHMMSS.csv`
- **Specifications**: Converted to WordPress custom fields
- **Ready for**: "My CSV Importer" plugin
- **Archive system**: Keeps 3 most recent, archives older versions

### Manual WordPress Conversion
```bash
# Convert Trek data
python3 -c "from wordpress_csv_converter import convert_latest_to_wordpress; convert_latest_to_wordpress('trek')"

# Convert Canyon data  
python3 -c "from wordpress_csv_converter import convert_latest_to_wordpress; convert_latest_to_wordpress('canyon')"
```

## 📊 **Data Extracted**

### Common Data (Both Scrapers)
- ✅ **Bike name and model**
- ✅ **Pricing information**
- ✅ **Category classification** 
- ✅ **Technical specifications**
- ✅ **Product descriptions**
- ✅ **High-resolution images**
- ✅ **Brand and series info**

### Trek-Specific Features
- ✅ **Complete dataLayer extraction**
- ✅ **Color variant detection**
- ✅ **Intelligent specification parsing**
- ✅ **Frame geometry analysis**
- ✅ **Drivetrain classification**

### Canyon-Specific Features  
- ✅ **Multi-series navigation** (Endurace, Ultimate, Aeroad, etc.)
- ✅ **Hierarchical scraping** (Categories → Series → Individual bikes)
- ✅ **Dutch language parsing**
- 🔧 **Price extraction** (in development)
- 🔧 **Enhanced specifications** (in development)

## 🗄️ **Archive System**

- **Automatic**: Runs with each scraper execution
- **Preserves**: Complete historical record
- **Organizes**: By brand and file type
- **Manages**: Disk space efficiently
- **Keeps**: 3 most recent in working directories

## 📋 **Requirements**

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing  
- `pandas` - Data manipulation
- `openpyxl` - Excel file handling

## 🎯 **Use Cases**

### 🏪 **E-commerce**
- Import bike catalogs to WordPress/WooCommerce
- Automated inventory updates
- Multi-brand product management

### 📊 **Market Research**
- Price monitoring and analysis
- Specification comparisons
- Market trend tracking

### 🛠️ **Development**
- API data source for bike databases
- Product recommendation systems
- Inventory management tools

## 📈 **Roadmap**

### Canyon Scraper Improvements
- 🔧 Enhanced price extraction
- 🔧 Advanced specification parsing
- 🔧 Color variant detection
- 🔧 Additional bike categories

### Multi-Brand Expansion
- 🚀 Specialized scraper
- 🚀 Giant scraper  
- 🚀 Cannondale scraper
- 🚀 Unified multi-brand interface

### WordPress Enhancements
- 🚀 WooCommerce direct integration
- 🚀 Custom field grouping
- 🚀 Image optimization
- 🚀 SEO optimization

## 🤝 **Contributing**

The scraper architecture is designed for easy extension:

1. **Copy base scraper**: Use `trek_bikes_scraper.py` as template
2. **Adapt selectors**: Update CSS selectors for target website
3. **Customize extraction**: Modify data extraction methods
4. **Update file paths**: Change brand folder names
5. **Test integration**: Ensure WordPress converter compatibility

## 📝 **Documentation**

- 📖 **WordPress Import Guide**: `WordPress_Import_Instructions.md`
- 🧪 **Testing**: Built-in test functions in each scraper
- 📊 **Logging**: Comprehensive logging to `*_scraper.log` files

## ⚠️ **Important Notes**

- **Respectful scraping**: Built-in delays between requests
- **Error handling**: Comprehensive exception management  
- **Data preservation**: No data loss with archive system
- **WordPress ready**: All exports immediately usable
- **Modular design**: Easy to extend and customize

## 🎉 **Status Summary**

| Scraper | Status | WordPress | Archive | Images | Specs |
|---------|--------|-----------|---------|--------|-------|
| **Trek** | ✅ Production | ✅ Auto | ✅ Auto | ✅ Full | ✅ Complete |
| **Canyon** | 🧪 Beta | ✅ Auto | ✅ Auto | ✅ Full | 🔧 In Progress |

Both scrapers provide **complete end-to-end solutions** from data scraping to WordPress-ready import files with professional file organization and comprehensive data preservation! 