# Unified WordPress Import Instructions

## 🌟 Overview
This document explains how to import bike data into WordPress using the **NEW unified master database system**. The unified system allows you to import data from all brands at once or filter by specific brands, all from a single comprehensive database.

## ✨ New Unified Features

### 🔄 **Unified Database Foundation**
- **Single Source**: All brands combined in one master database (`data/unified/master_all_brands_bikes.csv`)
- **Perfect Synchronization**: All brands share identical column structure (66 non-image columns)
- **Consistent Data**: DD-MM-YYYY date format across all brands
- **Status Tracking**: Available/Discontinued status for all bikes

### 📊 **Flexible WordPress Export Options**
- **Individual Brand Files**: Export just Trek or Canyon for brand-specific sites
- **Multi-Brand File**: Export all brands together for comprehensive sites
- **Available Bikes Only**: Automatically filters out discontinued bikes for clean WordPress catalogs

### 🎯 **Three WordPress File Types Generated**
1. `unified_trek_wordpress_[timestamp].csv` - Trek bikes only
2. `unified_canyon_wordpress_[timestamp].csv` - Canyon bikes only  
3. `unified_all_brands_wordpress_[timestamp].csv` - All brands combined

## 🚀 Quick Start Guide

### 1. Generate Unified WordPress Files
```bash
python3 unified_wordpress_converter.py
```

**This single command creates:**
- ✅ Individual brand WordPress files (Trek, Canyon)
- ✅ Combined all-brands WordPress file
- ✅ Automatic archiving of old files
- ✅ All files ready for WordPress import

### 2. Choose Your Import File
Look in `data/wordpress_imports/` for:
- **`unified_trek_wordpress_*.csv`** - For Trek-only WordPress sites
- **`unified_canyon_wordpress_*.csv`** - For Canyon-only WordPress sites  
- **`unified_all_brands_wordpress_*.csv`** - For multi-brand WordPress sites

### 3. Import to WordPress
Use any of these files with your WordPress CSV importer plugin.

## 📁 File Structure

```
data/
├── unified/                              # 🌟 NEW: Unified master database
│   ├── master_all_brands_bikes.csv       # Main unified database
│   ├── master_all_brands_bikes.xlsx      # Excel version
│   ├── master_all_brands_bikes.json      # JSON version
│   └── unified_database_summary.txt      # Statistics summary
├── wordpress_imports/                    # WordPress-ready files
│   ├── unified_trek_wordpress_*.csv      # 🆕 Trek from unified DB
│   ├── unified_canyon_wordpress_*.csv    # 🆕 Canyon from unified DB
│   ├── unified_all_brands_wordpress_*.csv # 🆕 All brands from unified DB
│   ├── trek_bikes_wordpress_*.csv        # Legacy individual files
│   └── canyon_bikes_wordpress_*.csv      # Legacy individual files
└── archive/                              # Archived older files
    └── wordpress_imports/                # Archived WordPress files
```

## 📊 WordPress Format Structure

### Core Product Fields
- `post_title` - Product name (e.g., "Ultimate CF SLX 8 AXS")
- `post_content` - Product description
- `post_status` - Set to "publish"
- `post_type` - Set to "product" (for WooCommerce)
- `sku` - Product SKU
- `regular_price` - Product price
- `product_cat` - Product category
- `brand` - Brand name (Trek, Canyon, etc.)
- `variant` - Product variant
- `color` - Product color

### Status Tracking Custom Fields (NEW!)
- `meta:availability_status` - Current status (Available)
- `meta:first_seen_date` - When bike was first discovered (DD-MM-YYYY)
- `meta:last_seen_date` - When bike was last seen available (DD-MM-YYYY)
- `meta:last_updated` - Last database update (DD-MM-YYYY)

### Specification Custom Fields
All bike specifications are converted to custom fields with the `meta:` prefix:

**Frame & Build:**
- `meta:Frame` - Frame material and series
- `meta:Framefit` - Frame geometry type  
- `meta:Gewicht` - Weight
- `meta:Gewichtslimiet` - Weight limit
- `meta:Material` - Frame material detail
- `meta:Weight` - Alternative weight field

**Drivetrain:**
- `meta:Shifter` - Shifter type
- `meta:Shifter_speed` - Speed count
- `meta:Voorderailleur` - Front derailleur
- `meta:Achterderailleur` - Rear derailleur
- `meta:Crankstel` - Crankset
- `meta:Cassette` - Cassette specs
- `meta:Ketting` - Chain type
- `meta:Maximale_maat_kettingblad` - Max chainring size

**Wheels & Tires:**
- `meta:Naaf_voor` - Front hub
- `meta:Naaf_achter` - Rear hub
- `meta:As_voorwiel` - Front axle
- `meta:Velg` - Rim specifications
- `meta:Buitenband` - Tire specifications
- `meta:Maximale_bandenmaat` - Maximum tire size

**E-bike Components (Trek specific):**
- `meta:Accu` - Battery specifications
- `meta:Motor` - Motor details
- `meta:Oplader` - Charger information

**Detailed Components:**
- `meta:Voorvork` - Fork details
- `meta:Remschijf` - Brake disc specs
- `meta:Computer` - Bike computer
- `meta:Bidonhouder` - Bottle cage
- And 15+ more detailed component specifications

**Images:**
- `images` - Main product image URL
- `meta:additional_image_2` to `meta:additional_image_10` - Additional images
- `meta:image_1_local_path` to `meta:image_10_local_path` - Local image paths

### Import Metadata
- `meta:import_date` - When WordPress file was generated (DD-MM-YYYY)
- `meta:import_source` - Source: "unified_master_database"
- `meta:import_brands` - Which brands were included in this export

## 🎯 Usage Scenarios

### Scenario 1: Single Brand WordPress Site
If you're running a Trek-only or Canyon-only WordPress site:

```bash
python3 unified_wordpress_converter.py
```

Then import: `unified_trek_wordpress_*.csv` or `unified_canyon_wordpress_*.csv`

### Scenario 2: Multi-Brand WordPress Site
If you're running a site with multiple bike brands:

```bash
python3 unified_wordpress_converter.py
```

Then import: `unified_all_brands_wordpress_*.csv`

### Scenario 3: Custom Brand Selection
If you want to generate a file with specific brands only:

```python
from unified_wordpress_converter import convert_unified_to_wordpress_format

# Generate WordPress file for specific brands
wp_df, output_file = convert_unified_to_wordpress_format(
    brands=['Trek', 'Canyon'],  # Specify brands
    verbose=True
)
```

## 📈 Benefits Over Previous System

### 🎯 **Data Quality Improvements**
- **Perfect Column Parity**: All brands have identical 66 non-image columns
- **Consistent Dates**: All dates in DD-MM-YYYY format
- **Status Tracking**: Know exactly when bikes became available/discontinued
- **No Data Loss**: Complete specification coverage for all brands

### 🚀 **Workflow Improvements** 
- **Single Command**: Generate all WordPress formats at once
- **Flexible Options**: Individual brands or combined multi-brand files
- **Unified Source**: One database powers all WordPress exports
- **Future Ready**: Easy to add new brands to the unified structure

### 📊 **WordPress Benefits**
- **79 Custom Fields**: Complete specification coverage
- **Brand Filtering**: Filter products by brand in WordPress
- **Status Tracking**: Know bike availability history
- **Image Support**: Up to 10 images per bike (vs previous 5)
- **Better Organization**: Logical specification grouping

## 🔧 Advanced Usage

### Generate Specific Brand Only
```python
from unified_wordpress_converter import convert_by_brand

# Generate Trek WordPress file only
trek_file = convert_by_brand('Trek', verbose=True)

# Generate Canyon WordPress file only  
canyon_file = convert_by_brand('Canyon', verbose=True)
```

### Generate All Brands Combined
```python
from unified_wordpress_converter import convert_all_brands

# Generate unified all-brands WordPress file
all_brands_file = convert_all_brands(verbose=True)
```

### Custom Output Location
```python
from unified_wordpress_converter import convert_unified_to_wordpress_format

# Generate with custom output path
wp_df, output_file = convert_unified_to_wordpress_format(
    input_file="data/unified/master_all_brands_bikes.csv",
    output_file="custom/path/my_wordpress_import.csv",
    brands=['Trek'],
    verbose=True
)
```

## 📋 Import Steps

### 1. Install Required Plugins
```
- My CSV Importer (for basic CSV import)
- WooCommerce (if importing as products)
- Advanced Custom Fields or similar (for managing custom fields)
```

### 2. WordPress Import Process
1. Go to **Tools > Import** in WordPress admin
2. Choose **CSV** importer
3. Upload your chosen file from: `data/wordpress_imports/unified_*_wordpress_*.csv`
4. Map the columns:
   - `post_title` → Post Title
   - `post_content` → Post Content
   - `post_type` → Post Type
   - `sku` → Product SKU
   - `regular_price` → Regular Price
   - `brand` → Product Brand
   - All `meta:*` fields → Custom Fields

### 3. Custom Field Groups Recommendation

Organize the 79 custom fields into logical groups:

**🏗️ Frame & Build**
- Frame, Framefit, Gewicht, Gewichtslimiet, Material, Weight

**⚙️ Drivetrain**  
- Shifter, Shifter_speed, Voorderailleur, Achterderailleur, Crankstel, Cassette, Ketting

**🚴 Wheels & Contact Points**
- Naaf_voor, Naaf_achter, Velg, Buitenband, Zadel, Stuur, Rem

**🔋 E-bike Components**
- Accu, Motor, Oplader, Computer

**📊 Tracking & Status**
- availability_status, first_seen_date, last_seen_date, last_updated

**📷 Images & Media**
- additional_image_2 through additional_image_10, image_*_local_path

## 🔍 Verification & Quality Control

### Data Quality Checks
```bash
# Check unified database statistics
cat data/unified/unified_database_summary.txt

# Verify WordPress file generation
ls -la data/wordpress_imports/unified_*_wordpress_*.csv

# Check brand distribution in unified file
python3 -c "import pandas as pd; df=pd.read_csv('data/wordpress_imports/unified_all_brands_wordpress_*.csv'); print(df['brand'].value_counts())"
```

### Field Verification
All WordPress files should have:
- **Core fields**: 8 basic WordPress/WooCommerce fields
- **Custom fields**: 79 meta fields (specifications + tracking + images)
- **Total columns**: ~87 columns per file
- **Only available bikes**: No discontinued bikes in WordPress exports

## 🚨 Troubleshooting

### Common Issues
- **"Unified database not found"**: Run the unified database creation first
- **Missing specifications**: Some brands may not have all 66 spec fields populated
- **Image URLs**: Some image URLs may be empty (normal for older/limited bikes)
- **Custom field overload**: WordPress may need custom field plugins for 79+ fields

### Alternative Approaches
- **WooCommerce CSV Importer**: Use built-in WooCommerce importer for product-specific features
- **WP All Import**: Premium plugin with advanced field mapping capabilities
- **Batch Import**: Import brands separately if all-brands file is too large

## 📊 Data Summary

### Current Database Stats
- **Total Bikes**: 120 (96 available for WordPress)
- **Brands**: 2 (Trek: 67 bikes, Canyon: 53 bikes)  
- **Specifications**: 66 unified specification fields
- **Custom Fields**: 79 total WordPress custom fields
- **Images**: Up to 10 images per bike
- **Status Tracking**: Complete availability history
- **Date Format**: DD-MM-YYYY throughout

### WordPress Export Stats  
- **Trek WordPress**: 48 available bikes
- **Canyon WordPress**: 48 available bikes
- **All Brands WordPress**: 96 available bikes
- **Discontinued Bikes**: Excluded from WordPress (tracked in master DB)

## 🎉 Migration from Legacy System

If you were using the old individual brand WordPress converters:

### Old Way (Per Brand)
```bash
python3 trek_bikes_scraper.py        # Run scraper
python3 wordpress_csv_converter.py   # Convert to WordPress
# Repeat for each brand separately
```

### New Way (Unified)
```bash
python3 run_all_scrapers.py          # Run all scrapers + unified DB
python3 unified_wordpress_converter.py # Generate all WordPress formats
```

**Benefits**: Single workflow, consistent data, multi-brand support, better tracking!

---

The unified WordPress import system provides a complete, scalable solution for importing comprehensive bike data into WordPress with full specification coverage, status tracking, and multi-brand support! 