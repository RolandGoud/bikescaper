#!/usr/bin/env python3
"""
WordPress CSV Converter
Converts Trek bikes CSV to WordPress-ready format with specifications as custom fields
"""

import pandas as pd
import sys
import os
import shutil
import glob
from datetime import datetime

def convert_to_wordpress_format(input_file, output_file, verbose=True):
    """Convert the CSV to WordPress-ready format with custom fields"""
    
    if verbose:
        print(f"Reading CSV file: {input_file}")
    df = pd.read_csv(input_file)
    
    # Create new DataFrame for WordPress format
    wp_df = pd.DataFrame()
    
    # Basic product fields
    wp_df['post_title'] = df['name']
    wp_df['post_content'] = df['description'].fillna('')
    wp_df['post_status'] = 'publish'
    wp_df['post_type'] = 'product'  # Assuming WooCommerce products
    
    # Product-specific fields
    wp_df['sku'] = df['sku']
    wp_df['regular_price'] = df['price']
    wp_df['product_cat'] = df['category']
    wp_df['brand'] = df['brand']
    wp_df['product_url'] = df['url']
    wp_df['variant'] = df['variant']
    wp_df['color'] = df['color']
    
    # Convert all spec_ columns to custom fields with meta: prefix
    spec_columns = [col for col in df.columns if col.startswith('spec_')]
    for spec_col in spec_columns:
        # Remove 'spec_' prefix and create meta field name
        field_name = spec_col.replace('spec_', '')
        wp_df[f'meta:{field_name}'] = df[spec_col]
    
    # Handle main product images (first 5 hero images)
    image_columns = []
    for i in range(1, 6):  # First 5 images
        url_col = f'hero_image_{i}_url'
        path_col = f'hero_image_{i}_path'
        filename_col = f'hero_image_{i}_filename'
        
        if url_col in df.columns:
            if i == 1:
                wp_df['images'] = df[url_col]  # Main product image
            else:
                wp_df[f'meta:additional_image_{i}'] = df[url_col]
            
            # Also store local paths as custom fields
            if path_col in df.columns:
                wp_df[f'meta:image_{i}_local_path'] = df[path_col]
    
    # Add import metadata
    wp_df['meta:import_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    wp_df['meta:import_source'] = 'trek_scraper'
    
    # Remove rows where title is empty
    wp_df = wp_df[wp_df['post_title'].notna()]
    
    if verbose:
        print(f"Converting {len(df)} products to WordPress format")
        print(f"Found {len(spec_columns)} specification fields")
    
    # Save to new CSV file
    wp_df.to_csv(output_file, index=False)
    if verbose:
        print(f"WordPress-ready CSV saved to: {output_file}")
        
        # Print summary
        print("\n=== CONVERSION SUMMARY ===")
        print(f"Products converted: {len(wp_df)}")
        print(f"Specification fields converted to custom fields: {len(spec_columns)}")
        print(f"Custom fields created: {len([col for col in wp_df.columns if col.startswith('meta:')])}")
        
        print("\n=== CUSTOM FIELDS CREATED ===")
        custom_fields = [col.replace('meta:', '') for col in wp_df.columns if col.startswith('meta:')]
        for field in sorted(custom_fields):
            print(f"- {field}")
    
    return wp_df

def clean_old_wordpress_files(keep_count=3, verbose=True):
    """Archive old WordPress CSV files, keeping only the most recent ones in working directory"""
    wp_dir = 'data/wordpress_imports'
    archive_dir = 'data/archive/wordpress_imports'
    
    # Handle both Trek and Canyon WordPress files
    patterns = [
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
                    print(f"Archived old WordPress file: {old_file} → {archive_path}")
            except OSError as e:
                if verbose:
                    print(f"Warning: Could not archive {old_file}: {e}")
        
        if verbose and files_archived > 0:
            print(f"✅ Archived {files_archived} old WordPress CSV files (kept {keep_count} most recent)")
    elif verbose:
        print(f"📁 Found {len(all_files)} WordPress CSV files (no archiving needed)")

def convert_latest_to_wordpress(brand="trek", verbose=True):
    """Convert the latest CSV file to WordPress format automatically"""
    if brand.lower() == "canyon":
        input_file = "data/canyon_bikes_latest.csv"
        output_prefix = "canyon_bikes_wordpress"
    else:
        input_file = "data/trek_bikes_latest.csv"
        output_prefix = "trek_bikes_wordpress"
    
    if not os.path.exists(input_file):
        if verbose:
            print(f"❌ Warning: {input_file} not found - skipping WordPress conversion")
        return None
    
    # Ensure WordPress imports directory exists
    wp_dir = 'data/wordpress_imports'
    os.makedirs(wp_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"{wp_dir}/{output_prefix}_{timestamp}.csv"
    
    try:
        if verbose:
            print(f"\n🔄 Converting to WordPress format...")
        convert_to_wordpress_format(input_file, output_file, verbose=verbose)
        
        # Clean up old WordPress files
        clean_old_wordpress_files(keep_count=3, verbose=verbose)
        
        if verbose:
            print(f"✅ WordPress conversion completed: {output_file}")
        return output_file
        
    except Exception as e:
        if verbose:
            print(f"❌ Error during WordPress conversion: {str(e)}")
        return None

def main():
    input_file = "data/trek_bikes_latest.csv"
    
    # Ensure WordPress imports directory exists
    wp_dir = 'data/wordpress_imports'
    os.makedirs(wp_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"{wp_dir}/trek_bikes_wordpress_{timestamp}.csv"
    
    try:
        result_df = convert_to_wordpress_format(input_file, output_file)
        print(f"\n✅ Conversion completed successfully!")
        print(f"📁 WordPress-ready file: {output_file}")
        print(f"🔧 Ready for import with 'My CSV Importer' plugin")
        
    except FileNotFoundError:
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 