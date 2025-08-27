#!/usr/bin/env python3
"""
Unified WordPress CSV Converter
Converts the unified master database to WordPress-ready format with specifications as custom fields
Supports filtering by brand or importing all brands together
"""

import pandas as pd
import sys
import os
import shutil
import glob
from datetime import datetime
from pathlib import Path

def convert_unified_to_wordpress_format(input_file=None, output_file=None, brands=None, verbose=True):
    """Convert the unified master database to WordPress-ready format with custom fields
    
    Args:
        input_file: Path to unified master file (defaults to data/unified/master_all_brands_bikes.csv)
        output_file: Output file path (auto-generated if not provided)
        brands: List of brands to include (e.g., ['Trek', 'Canyon']) or None for all brands
        verbose: Print detailed information
    """
    
    # Default input file
    if input_file is None:
        input_file = "data/unified/master_all_brands_bikes.csv"
    
    if verbose:
        print(f"📊 Reading unified master database: {input_file}")
    
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Unified master database not found: {input_file}")
    
    df = pd.read_csv(input_file)
    
    # Filter by brands if specified
    if brands:
        original_count = len(df)
        df = df[df['brand'].isin(brands)]
        if verbose:
            print(f"   🎯 Filtered to {brands}: {len(df)}/{original_count} bikes")
    
    # Filter to only available bikes (exclude discontinued for WordPress)
    available_df = df[df['status'] == 'Available'].copy()
    if verbose:
        print(f"   ✅ Available bikes only: {len(available_df)}/{len(df)} bikes")
    
    # Create new DataFrame for WordPress format
    wp_df = pd.DataFrame()
    
    # Basic product fields
    wp_df['post_title'] = available_df['name']
    wp_df['post_content'] = available_df['description'].fillna('')
    wp_df['post_status'] = 'publish'
    wp_df['post_type'] = 'product'  # For WooCommerce products
    
    # Product-specific fields
    wp_df['sku'] = available_df['sku']
    wp_df['regular_price'] = available_df['price']
    wp_df['product_cat'] = available_df['category']
    wp_df['brand'] = available_df['brand']
    wp_df['product_url'] = available_df['url']
    wp_df['variant'] = available_df['variant']
    wp_df['color'] = available_df['color']
    
    # Add status tracking as custom fields
    wp_df['meta:availability_status'] = available_df['status']
    wp_df['meta:first_seen_date'] = available_df['first_seen_date']
    wp_df['meta:last_seen_date'] = available_df['last_seen_date']
    wp_df['meta:last_updated'] = available_df['last_updated']
    
    # Convert all spec_ columns to custom fields with meta: prefix
    spec_columns = [col for col in available_df.columns if col.startswith('spec_')]
    for spec_col in spec_columns:
        # Remove 'spec_' prefix and create meta field name
        field_name = spec_col.replace('spec_', '')
        wp_df[f'meta:{field_name}'] = available_df[spec_col]
    
    # Handle main product images (first 10 hero images to cover more brands)
    image_columns_processed = 0
    for i in range(1, 11):  # First 10 images
        url_col = f'hero_image_{i}_url'
        path_col = f'hero_image_{i}_path'
        filename_col = f'hero_image_{i}_filename'
        
        if url_col in available_df.columns:
            # Only include if there's actual image data
            non_empty_images = available_df[url_col].dropna()
            if len(non_empty_images) > 0:
                if i == 1:
                    wp_df['images'] = available_df[url_col]  # Main product image
                else:
                    wp_df[f'meta:additional_image_{i}'] = available_df[url_col]
                
                # Also store local paths as custom fields
                if path_col in available_df.columns:
                    wp_df[f'meta:image_{i}_local_path'] = available_df[path_col]
                
                image_columns_processed += 1
    
    # Add import metadata
    wp_df['meta:import_date'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    wp_df['meta:import_source'] = 'unified_master_database'
    wp_df['meta:import_brands'] = ', '.join(brands) if brands else 'all_brands'
    
    # Remove rows where title is empty
    wp_df = wp_df[wp_df['post_title'].notna()]
    
    # Generate output filename if not provided
    if output_file is None:
        # Ensure WordPress imports directory exists
        wp_dir = 'data/wordpress_imports'
        os.makedirs(wp_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if brands:
            brand_suffix = '_'.join([b.lower() for b in brands])
            output_file = f"{wp_dir}/unified_{brand_suffix}_wordpress_{timestamp}.csv"
        else:
            output_file = f"{wp_dir}/unified_all_brands_wordpress_{timestamp}.csv"
    
    if verbose:
        print(f"🔄 Converting {len(available_df)} products to WordPress format")
        print(f"   📊 Found {len(spec_columns)} specification fields")
        print(f"   📸 Processed {image_columns_processed} image columns")
    
    # Save to new CSV file with proper quoting
    wp_df.to_csv(output_file, index=False, quoting=1)  # QUOTE_ALL
    
    if verbose:
        print(f"✅ WordPress-ready CSV saved to: {output_file}")
        
        # Print summary
        print("\n📋 CONVERSION SUMMARY:")
        print(f"   Products converted: {len(wp_df)}")
        print(f"   Brands included: {wp_df['brand'].unique().tolist()}")
        print(f"   Specification fields: {len(spec_columns)}")
        print(f"   Custom fields created: {len([col for col in wp_df.columns if col.startswith('meta:')])}")
        print(f"   Image columns processed: {image_columns_processed}")
        
        # Brand breakdown
        brand_counts = wp_df['brand'].value_counts()
        print(f"\n🏆 BRAND BREAKDOWN:")
        for brand, count in brand_counts.items():
            percentage = (count / len(wp_df)) * 100
            print(f"   • {brand}: {count} bikes ({percentage:.1f}%)")
        
        print(f"\n🔧 CUSTOM FIELDS CREATED:")
        custom_fields = sorted([col.replace('meta:', '') for col in wp_df.columns if col.startswith('meta:')])
        for field in custom_fields:
            print(f"   - {field}")
    
    return wp_df, output_file

def convert_by_brand(brand_name, verbose=True):
    """Convert unified database to WordPress format for a specific brand"""
    if verbose:
        print(f"🎯 CONVERTING {brand_name.upper()} TO WORDPRESS FORMAT")
        print("=" * 50)
    
    try:
        wp_df, output_file = convert_unified_to_wordpress_format(
            brands=[brand_name], 
            verbose=verbose
        )
        
        if verbose:
            print(f"\n✅ {brand_name} WordPress conversion completed!")
            print(f"📁 File: {output_file}")
        
        return output_file
        
    except Exception as e:
        if verbose:
            print(f"❌ Error converting {brand_name}: {str(e)}")
        return None

def convert_all_brands(verbose=True):
    """Convert unified database to WordPress format for all brands"""
    if verbose:
        print(f"🌟 CONVERTING ALL BRANDS TO WORDPRESS FORMAT")
        print("=" * 45)
    
    try:
        wp_df, output_file = convert_unified_to_wordpress_format(
            brands=None,  # All brands
            verbose=verbose
        )
        
        if verbose:
            print(f"\n✅ All brands WordPress conversion completed!")
            print(f"📁 File: {output_file}")
        
        return output_file
        
    except Exception as e:
        if verbose:
            print(f"❌ Error converting all brands: {str(e)}")
        return None

def clean_old_wordpress_files(keep_count=3, verbose=True):
    """Archive old WordPress CSV files, keeping only the most recent ones in working directory"""
    wp_dir = 'data/wordpress_imports'
    archive_dir = 'data/archive/wordpress_imports'
    
    # Handle unified WordPress files and individual brand files
    patterns = [
        f'{wp_dir}/unified_*_wordpress_*.csv',
        f'{wp_dir}/trek_bikes_wordpress_*.csv',
        f'{wp_dir}/canyon_bikes_wordpress_*.csv'
    ]
    
    all_files = []
    for pattern in patterns:
        files = glob.glob(pattern)
        all_files.extend(files)
    
    if len(all_files) > keep_count:
        # Ensure archive directory exists
        os.makedirs(archive_dir, exist_ok=True)
        
        # Sort by modification time, newest first
        all_files.sort(key=os.path.getmtime, reverse=True)
        
        files_archived = 0
        # Move older files to archive
        for old_file in all_files[keep_count:]:
            try:
                filename = os.path.basename(old_file)
                archive_path = os.path.join(archive_dir, filename)
                
                # If file already exists in archive, add timestamp to avoid conflicts
                if os.path.exists(archive_path):
                    name, ext = os.path.splitext(filename)
                    archive_path = os.path.join(archive_dir, f"{name}_archived_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
                
                shutil.move(old_file, archive_path)
                files_archived += 1
                if verbose:
                    print(f"📦 Archived: {old_file} → {archive_path}")
            except OSError as e:
                if verbose:
                    print(f"⚠️  Warning: Could not archive {old_file}: {e}")
        
        if verbose and files_archived > 0:
            print(f"✅ Archived {files_archived} old WordPress CSV files (kept {keep_count} most recent)")
    elif verbose:
        print(f"📁 Found {len(all_files)} WordPress CSV files (no archiving needed)")

def generate_all_wordpress_formats(verbose=True):
    """Generate WordPress formats for all brands (individual + unified)"""
    if verbose:
        print("🚀 GENERATING ALL WORDPRESS FORMATS FROM UNIFIED DATABASE")
        print("=" * 60)
        print()
    
    results = []
    
    # Check if unified database exists
    unified_file = "data/unified/master_all_brands_bikes.csv"
    if not os.path.exists(unified_file):
        if verbose:
            print(f"❌ Unified database not found: {unified_file}")
            print("   Run the unified database creation script first!")
        return results
    
    # Get available brands from unified database
    df = pd.read_csv(unified_file)
    available_brands = df['brand'].unique().tolist()
    
    if verbose:
        print(f"📊 Found brands in unified database: {', '.join(available_brands)}")
        print()
    
    # Generate individual brand WordPress files
    for brand in available_brands:
        if verbose:
            print(f"🔄 Processing {brand}...")
        result = convert_by_brand(brand, verbose=False)
        if result:
            results.append(result)
            if verbose:
                print(f"   ✅ {brand}: {os.path.basename(result)}")
        else:
            if verbose:
                print(f"   ❌ {brand}: Failed")
        print()
    
    # Generate unified all-brands WordPress file
    if verbose:
        print(f"🔄 Processing unified all-brands file...")
    unified_result = convert_all_brands(verbose=False)
    if unified_result:
        results.append(unified_result)
        if verbose:
            print(f"   ✅ All brands: {os.path.basename(unified_result)}")
    else:
        if verbose:
            print(f"   ❌ All brands: Failed")
    
    # Clean up old files
    if verbose:
        print()
        print("🧹 Cleaning up old WordPress files...")
    clean_old_wordpress_files(keep_count=5, verbose=verbose)  # Keep more files since we have multiple formats
    
    if verbose:
        print()
        print("🎉 ALL WORDPRESS FORMATS GENERATED!")
        print(f"📁 Generated {len(results)} WordPress-ready files")
        print("📁 Files saved to: data/wordpress_imports/")
        
        print()
        print("🔧 USAGE OPTIONS:")
        print("   • Import individual brand files for brand-specific sites")
        print("   • Import unified file for multi-brand sites")
        print("   • All files ready for WordPress/WooCommerce import")
    
    return results

def main():
    """Main function - generate all WordPress formats by default"""
    try:
        results = generate_all_wordpress_formats(verbose=True)
        
        if results:
            print(f"\n✅ Success! Generated {len(results)} WordPress files")
            print("🔧 Ready for import with WordPress CSV importer plugins")
        else:
            print("\n❌ No WordPress files were generated")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error during WordPress conversion: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 