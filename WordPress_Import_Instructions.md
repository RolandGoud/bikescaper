# WordPress Import Instructions

## Overview
This document explains how to import the Trek bikes data into WordPress using the converted CSV file with the "My CSV Importer" plugin. **WordPress CSV files are now automatically generated every time you run the scraper!**

## ✨ Automated Features (NEW!)

### 🔄 **Automatic WordPress Conversion**
- WordPress-ready CSV files are automatically generated after each scrape
- No manual conversion needed - just run the scraper as usual
- Conversion happens silently in the background after data export

### 🧹 **Automatic Cleanup**
- Keeps only the **3 most recent versions** of all files
- Automatically removes older files to save disk space
- Applies to both regular export files and WordPress files
- Runs every time the scraper executes

### 📁 **File Management**
- **Latest files**: Always available as `trek_bikes_latest.*`
- **Timestamped archives**: 3 most recent versions kept
- **WordPress files**: `trek_bikes_wordpress_YYYYMMDD_HHMMSS.csv`

## Files Created
- **Original CSV**: `data/trek_bikes_latest.csv` (always current)
- **WordPress CSV**: `data/trek_bikes_wordpress_[timestamp].csv` (auto-generated)
- **Archives**: Timestamped versions (3 most recent kept)

## Quick Start (NEW Workflow!)

### 1. Run the Scraper (Everything Automated!)
```bash
python3 trek_bikes_scraper.py
```

**That's it!** The scraper will now:
- ✅ Scrape the latest bike data
- ✅ Save regular export files (JSON, CSV, Excel)
- ✅ **Automatically generate WordPress-ready CSV**
- ✅ **Clean up old files (keeping 3 most recent)**
- ✅ Log all activities

### 2. Find Your WordPress File
Look for the newest file matching: `data/trek_bikes_wordpress_*.csv`

### 3. Import to WordPress
Use the auto-generated WordPress CSV file with your import plugin.

## WordPress Format Structure

### Core Product Fields
- `post_title` - Product name (e.g., "Domane AL 2 Rim")
- `post_content` - Product description
- `post_status` - Set to "publish"
- `post_type` - Set to "product" (for WooCommerce)
- `sku` - Product SKU
- `regular_price` - Product price
- `product_cat` - Product category
- `brand` - Brand name (Trek)
- `variant` - Product variant
- `color` - Product color

### Custom Fields (Specifications)
All bike specifications are converted to custom fields with the `meta:` prefix:

**Frame & Build:**
- `meta:Frame` - Frame material and series
- `meta:Framefit` - Frame geometry type
- `meta:Gewicht` - Weight
- `meta:Gewichtslimiet` - Weight limit

**Drivetrain:**
- `meta:Shifter` - Shifter type
- `meta:Voorderailleur` - Front derailleur
- `meta:Achterderailleur` - Rear derailleur
- `meta:Crankstel` - Crankset
- `meta:Cassette` - Cassette specs
- `meta:Ketting` - Chain type

**Wheels & Tires:**
- `meta:Naaf_voor` - Front hub
- `meta:Naaf_achter` - Rear hub
- `meta:Velg` - Rim specifications
- `meta:Buitenband` - Tire specifications
- `meta:Maximale_bandenmaat` - Maximum tire size

**Contact Points:**
- `meta:Zadel` - Saddle type
- `meta:Stuur` - Handlebar type
- `meta:Stuurlint` - Bar tape
- `meta:Rem` - Brake type

**Images:**
- `images` - Main product image URL
- `meta:additional_image_2` to `meta:additional_image_5` - Additional images
- `meta:image_1_local_path` to `meta:image_5_local_path` - Local image paths

## Manual WordPress Conversion (If Needed)

If you need to manually convert a specific CSV file:

```bash
python3 wordpress_csv_converter.py
```

Or use it as a Python module:
```python
from wordpress_csv_converter import convert_latest_to_wordpress
result = convert_latest_to_wordpress()
```

## Import Steps

### 1. Install Required Plugins
```
- My CSV Importer (for basic CSV import)
- WooCommerce (if importing as products)
- Custom Field Suite or similar (for managing custom fields)
```

### 2. WordPress Import Process
1. Go to **Tools > Import** in WordPress admin
2. Choose **CSV** importer
3. Upload the newest file: `trek_bikes_wordpress_[timestamp].csv`
4. Map the columns:
   - `post_title` → Post Title
   - `post_content` → Post Content
   - `post_type` → Post Type
   - `sku` → Product SKU
   - `regular_price` → Regular Price
   - All `meta:*` fields → Custom Fields

### 3. Custom Field Configuration
After import, you may want to:
- Create custom field groups for better organization
- Set up display templates for specifications
- Configure which fields appear on product pages

### 4. Image Handling
The CSV contains both:
- **External URLs** (`images` field) - Direct links to Trek's CDN
- **Local paths** (`meta:image_*_local_path`) - If you've downloaded images locally

You may need to:
- Download images locally for better performance
- Update image URLs to your media library
- Set featured images for products

## File Management Details

### 🗂️ **Archive Strategy**
- **Keep Count**: 3 most recent versions of each file type
- **File Types Managed**: 
  - `trek_bikes_*.json` (data exports)
  - `trek_bikes_*.csv` (data exports)  
  - `trek_bikes_*.xlsx` (data exports)
  - `trek_bikes_wordpress_*.csv` (WordPress files)
- **Latest Files**: Never deleted (always current)

### 📊 **Logging**
All operations are logged to `trek_scraper.log`:
- WordPress conversion status
- File cleanup activities
- Error handling

## Custom Field Groups Suggestion

You might want to organize the custom fields into logical groups:

### **Frame & Geometry**
- Frame, Framefit, Gewicht, Gewichtslimiet

### **Drivetrain**
- Shifter, Voorderailleur, Achterderailleur, Crankstel, Cassette, Ketting

### **Wheels & Tires**
- Naaf_voor, Naaf_achter, Velg, Buitenband, Maximale_bandenmaat

### **Components**
- Zadel, Stuur, Stuurlint, Rem, Balhoofdstel

### **Additional Specs**
- All other technical specifications

## Post-Import Tasks

1. **Verify Import**
   - Check that all products were imported
   - Verify custom fields are properly assigned
   - Test that images display correctly

2. **Styling & Display**
   - Create templates to display specifications nicely
   - Group related specs together
   - Add styling for better readability

3. **SEO & Organization**
   - Set up proper categories/taxonomies
   - Configure product URLs
   - Add meta descriptions

## Troubleshooting

### Common Issues:
- **Missing custom fields**: Ensure your CSV importer supports the `meta:` prefix
- **Image problems**: Check image URLs and consider downloading locally
- **Product type issues**: Make sure WooCommerce is active if importing as products
- **WordPress conversion failed**: Check `trek_scraper.log` for details

### Alternative Import Methods:
- WooCommerce Product CSV Importer (built-in to WooCommerce)
- WP All Import (premium plugin with advanced mapping)
- Custom PHP import script

### Manual Operations:
```bash
# Force WordPress conversion
python3 -c "from wordpress_csv_converter import convert_latest_to_wordpress; convert_latest_to_wordpress()"

# Manual cleanup (keep 3 most recent)
python3 -c "from wordpress_csv_converter import clean_old_wordpress_files; clean_old_wordpress_files(3)"
```

## Data Summary
- **Total Products**: ~61 Trek bikes (varies with website updates)
- **Specification Fields**: ~51 technical specifications
- **Custom Fields Created**: ~62 total custom fields
- **Images**: Up to 5 images per product with both URLs and local paths
- **Auto-Generation**: WordPress CSV created after every scrape
- **File Management**: Automatic cleanup keeps 3 most recent versions

## 🎯 **Benefits of New Automated System**
- ✅ **Zero Manual Work**: WordPress files generated automatically
- ✅ **Always Current**: WordPress CSV matches latest scrape data
- ✅ **Disk Space Managed**: Old files automatically cleaned up
- ✅ **Version History**: 3 most recent versions always available
- ✅ **Error Handling**: All operations logged for troubleshooting
- ✅ **Backwards Compatible**: Manual conversion still available

The scraper now provides a complete end-to-end solution from data scraping to WordPress-ready import files! 