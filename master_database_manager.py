#!/usr/bin/env python3
"""
Master Database Manager for Bike Scraper
Comprehensive solution for tracking all bike models across all brands with discontinued status
"""

import pandas as pd
import json
import os
import csv
import re
from datetime import datetime
from pathlib import Path
import logging

class MasterDatabaseManager:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def get_brand_files(self, brand_name):
        """Get file paths for a specific brand with organized folder structure"""
        brand_lower = brand_name.lower()
        
        # Create brand-specific directory structure
        brand_dir = self.data_dir / brand_name
        master_dir = brand_dir / "master"
        reports_dir = brand_dir / "reports"
        historical_dir = brand_dir / "historical"
        
        # Create all subdirectories
        brand_dir.mkdir(exist_ok=True)
        master_dir.mkdir(exist_ok=True)
        reports_dir.mkdir(exist_ok=True)
        historical_dir.mkdir(exist_ok=True)
        
        return {
            'latest_csv': self.data_dir / f"{brand_lower}_bikes_latest.csv",
            'master_csv': master_dir / f"master_{brand_lower}_bikes_all.csv",
            'master_json': master_dir / f"master_{brand_lower}_bikes_all.json",
            'master_xlsx': master_dir / f"master_{brand_lower}_bikes_all.xlsx",
            'discontinued_csv': reports_dir / f"{brand_lower}_bikes_discontinued.csv",
            'new_csv': reports_dir / f"{brand_lower}_bikes_new.csv",
            'available_csv': reports_dir / f"{brand_lower}_bikes_available.csv",
            'status_report': reports_dir / f"{brand_lower}_status_summary.txt",
            'historical_dir': historical_dir
        }
    
    def load_master_database(self, brand_name):
        """Load existing master database or create empty DataFrame"""
        files = self.get_brand_files(brand_name)
        
        if files['master_csv'].exists():
            self.logger.info(f"📖 Loading existing master database: {files['master_csv']}")
            return pd.read_csv(files['master_csv'])
        else:
            self.logger.info(f"🆕 Creating new master database for {brand_name}")
            return pd.DataFrame()
    
    def load_archived_data(self, brand_name):
        """Load the most complete archived data for discontinued bikes"""
        brand_lower = brand_name.lower()
        
        # Look for archived data in multiple locations
        archive_patterns = [
            self.data_dir / "archive" / brand_name / f"{brand_lower}_bikes_*.csv",
            self.data_dir / brand_name / f"{brand_lower}_bikes_*.csv"
        ]
        
        best_archive = None
        best_score = 0
        
        for pattern in archive_patterns:
            parent_dir = pattern.parent
            if parent_dir.exists():
                for file_path in parent_dir.glob(pattern.name):
                    try:
                        # Score archives by completeness (bikes * columns)
                        df = pd.read_csv(file_path)
                        score = len(df) * len(df.columns)
                        
                        if score > best_score:
                            best_score = score
                            best_archive = file_path
                            
                    except Exception as e:
                        self.logger.warning(f"Could not read {file_path}: {e}")
        
        if best_archive:
            self.logger.info(f"📂 Using archived data: {best_archive}")
            return pd.read_csv(best_archive), best_archive.stem.split('_')[-1]  # Extract date
        
        return None, None
    
    def format_date_dd_mm_yyyy(self, date_str):
        """Convert date to DD-MM-YYYY format"""
        if pd.isna(date_str) or str(date_str) == 'Unknown':
            return 'Unknown'
        
        # Get current date in DD-MM-YYYY format
        current_date = datetime.now().strftime('%d-%m-%Y')
        
        date_str = str(date_str).strip()
        
        # If it's already in DD-MM-YYYY format, keep it
        if len(date_str) == 10 and date_str.count('-') == 2:
            parts = date_str.split('-')
            if len(parts[0]) == 2:  # DD-MM-YYYY
                return date_str
            elif len(parts[0]) == 4:  # YYYY-MM-DD
                return f'{parts[2]}-{parts[1]}-{parts[0]}'
        
        # If it's a new date, return current date
        return current_date
    
    def determine_bike_status(self, bike_name, current_bikes, master_df):
        """Determine the status of a bike (New, Available, Discontinued)"""
        is_current = bike_name in current_bikes
        was_known = len(master_df) > 0 and bike_name in master_df['name'].values
        
        current_date_dd_mm_yyyy = datetime.now().strftime('%d-%m-%Y')
        
        if is_current and not was_known:
            return 'New', current_date_dd_mm_yyyy, current_date_dd_mm_yyyy
        elif is_current and was_known:
            # Get existing dates
            existing_bike = master_df[master_df['name'] == bike_name].iloc[0]
            first_seen = self.format_date_dd_mm_yyyy(existing_bike.get('first_seen_date', current_date_dd_mm_yyyy))
            return 'Available', first_seen, current_date_dd_mm_yyyy
        else:
            # Discontinued - preserve last seen date
            if was_known:
                existing_bike = master_df[master_df['name'] == bike_name].iloc[0]
                first_seen = self.format_date_dd_mm_yyyy(existing_bike.get('first_seen_date', 'Unknown'))
                last_seen = self.format_date_dd_mm_yyyy(existing_bike.get('last_seen_date', 'Unknown'))
                return 'Discontinued', first_seen, last_seen
            else:
                return 'Discontinued', 'Unknown', 'Unknown'
    
    def update_master_database(self, brand_name, current_csv_path=None):
        """Update master database for a specific brand"""
        self.logger.info(f"🔄 Updating master database for {brand_name}...")
        
        files = self.get_brand_files(brand_name)
        
        # Load current data
        if current_csv_path:
            current_csv = Path(current_csv_path)
        else:
            current_csv = files['latest_csv']
            
        if not current_csv.exists():
            self.logger.error(f"❌ Current data file not found: {current_csv}")
            return False
        
        current_df = pd.read_csv(current_csv)
        master_df = self.load_master_database(brand_name)
        
        # Get archived data for better discontinued bike information
        archived_df, archive_date = self.load_archived_data(brand_name)
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_bikes = set(current_df['name'].tolist())
        
        # If we have archived data, find discontinued bikes with complete info
        if archived_df is not None:
            archived_bikes = set(archived_df['name'].tolist())
            discontinued_bikes = archived_bikes - current_bikes
            
            self.logger.info(f"📊 Analysis:")
            self.logger.info(f"   Current bikes: {len(current_bikes)}")
            self.logger.info(f"   Archived bikes: {len(archived_bikes)}")
            self.logger.info(f"   Discontinued bikes found: {len(discontinued_bikes)}")
        else:
            discontinued_bikes = set()
            archived_df = pd.DataFrame()
        
        # Combine all bikes we need to track
        if len(master_df) > 0:
            previously_known = set(master_df['name'].tolist())
        else:
            previously_known = set()
            
        all_bikes = current_bikes | discontinued_bikes | previously_known
        
        # Create updated records
        updated_records = []
        status_counts = {'New': 0, 'Available': 0, 'Discontinued': 0}
        
        for bike_name in all_bikes:
            status, first_seen, last_seen = self.determine_bike_status(
                bike_name, current_bikes, master_df
            )
            
            # Get bike data from appropriate source
            if bike_name in current_bikes:
                # Current bike - use current data
                current_bike_data = current_df[current_df['name'] == bike_name].iloc[0]
                bike_record = current_bike_data.to_dict()
                
                # Add/update master database specific fields
                bike_record['status'] = status
                bike_record['first_seen_date'] = first_seen
                bike_record['last_seen_date'] = last_seen
                bike_record['last_updated'] = current_date
                
                # Ensure brand is set
                if 'brand' not in bike_record or not bike_record['brand']:
                    bike_record['brand'] = brand_name
                    
            elif bike_name in discontinued_bikes and len(archived_df) > 0:
                # Discontinued bike - use archived data
                archived_bike_data = archived_df[archived_df['name'] == bike_name].iloc[0]
                bike_record = archived_bike_data.to_dict()
                
                bike_record['status'] = 'Discontinued'
                bike_record['first_seen_date'] = archive_date if archive_date else first_seen
                bike_record['last_seen_date'] = archive_date if archive_date else last_seen
                bike_record['last_updated'] = current_date
                
                if 'brand' not in bike_record or not bike_record['brand']:
                    bike_record['brand'] = brand_name
                    
            elif len(master_df) > 0 and bike_name in master_df['name'].values:
                # Previously known bike - preserve existing data
                existing_bike = master_df[master_df['name'] == bike_name].iloc[0]
                bike_record = existing_bike.to_dict()
                bike_record['status'] = status
                bike_record['last_updated'] = current_date
                
            else:
                # Should not happen, but create minimal record
                bike_record = {
                    'name': bike_name,
                    'brand': brand_name,
                    'status': status,
                    'first_seen_date': first_seen,
                    'last_seen_date': last_seen,
                    'last_updated': current_date
                }
            
            updated_records.append(bike_record)
            status_counts[status] += 1
        
        # Create updated master database
        updated_master_df = pd.DataFrame(updated_records)
        
        # Save master database with safe CSV export
        self.safe_csv_export(updated_master_df, files['master_csv'])
        
        # Save Excel version
        updated_master_df.to_excel(files['master_xlsx'], index=False, engine='openpyxl', sheet_name='Master Database')
        
        # Save JSON version
        updated_master_df.to_json(files['master_json'], orient='records', indent=2)
        
        self.logger.info("✅ Master database updated!")
        self.logger.info(f"   📈 New bikes: {status_counts['New']}")
        self.logger.info(f"   ✅ Available bikes: {status_counts['Available']}")
        self.logger.info(f"   🔴 Discontinued bikes: {status_counts['Discontinued']}")
        self.logger.info(f"   📁 CSV saved to: {files['master_csv']}")
        self.logger.info(f"   📊 Excel saved to: {files['master_xlsx']}")
        
        # Generate status reports
        self.generate_status_reports(brand_name, updated_master_df)
        
        return True
    
    def generate_status_reports(self, brand_name, master_df=None):
        """Generate detailed status reports for a brand"""
        files = self.get_brand_files(brand_name)
        
        if master_df is None:
            master_df = self.load_master_database(brand_name)
        
        if len(master_df) == 0:
            self.logger.warning(f"No data found for {brand_name}")
            return
        
        # Create status-specific files
        available_bikes = master_df[master_df['status'] == 'Available']
        new_bikes = master_df[master_df['status'] == 'New']
        discontinued_bikes = master_df[master_df['status'] == 'Discontinued'].copy()
        
        # Add discontinued date column for discontinued bikes (based on last_seen_date)
        if len(discontinued_bikes) > 0:
            discontinued_bikes['date_discontinued'] = discontinued_bikes['last_seen_date']
            # Move date_discontinued to second column for better visibility
            cols = discontinued_bikes.columns.tolist()
            if 'date_discontinued' in cols:
                cols.remove('date_discontinued')
            cols.insert(1, 'date_discontinued')
            discontinued_bikes = discontinued_bikes[cols]
        
        # Save status-specific CSVs with safe export
        self.safe_csv_export(available_bikes, files['available_csv'])
        self.safe_csv_export(new_bikes, files['new_csv'])
        self.safe_csv_export(discontinued_bikes, files['discontinued_csv'])
        
        # Also save Excel versions for better data handling
        excel_files = {
            'available_excel': files['available_csv'].with_suffix('.xlsx'),
            'new_excel': files['new_csv'].with_suffix('.xlsx'),
            'discontinued_excel': files['discontinued_csv'].with_suffix('.xlsx')
        }
        
        try:
            available_bikes.to_excel(excel_files['available_excel'], index=False, engine='openpyxl', sheet_name='Available Bikes')
            new_bikes.to_excel(excel_files['new_excel'], index=False, engine='openpyxl', sheet_name='New Bikes')
            discontinued_bikes.to_excel(excel_files['discontinued_excel'], index=False, engine='openpyxl', sheet_name='Discontinued Bikes')
            self.logger.info("📊 Excel versions created for all status reports")
        except Exception as e:
            self.logger.warning(f"Could not create Excel files: {e}")
        
        # Generate summary report
        with open(files['status_report'], 'w') as f:
            f.write(f"{brand_name} Bikes Status Summary\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("📊 OVERVIEW:\n")
            f.write(f"Total bikes tracked: {len(master_df)}\n")
            f.write(f"Available: {len(available_bikes)}\n")
            f.write(f"New: {len(new_bikes)}\n")
            f.write(f"Discontinued: {len(discontinued_bikes)}\n\n")
            
            if len(new_bikes) > 0:
                f.write("🆕 NEW BIKES:\n")
                for _, bike in new_bikes.iterrows():
                    price = f"€{bike['price']}" if pd.notna(bike.get('price')) else "Price N/A"
                    f.write(f"   • {bike['name']} ({price}) - Added {bike['first_seen_date']}\n")
                f.write("\n")
            
            if len(discontinued_bikes) > 0:
                f.write("🔴 DISCONTINUED BIKES:\n")
                for _, bike in discontinued_bikes.iterrows():
                    price = f"€{bike['price']}" if pd.notna(bike.get('price')) else "Price N/A"
                    f.write(f"   ❌ {bike['name']} ({price}) - Last seen {bike['last_seen_date']}\n")
                f.write("\n")
        
        self.logger.info("📋 Status Reports Generated:")
        self.logger.info(f"   ✅ Available models: {files['available_csv']} ({len(available_bikes)} bikes)")
        self.logger.info(f"   🆕 New models: {files['new_csv']} ({len(new_bikes)} bikes)")
        self.logger.info(f"   🔴 Discontinued models: {files['discontinued_csv']} ({len(discontinued_bikes)} bikes)")
        self.logger.info(f"   📄 Summary report: {files['status_report']}")
    
    def update_all_brands(self):
        """Update master databases for all detected brands"""
        self.logger.info("🚀 Updating master databases for all brands...")
        
        brands_updated = []
        
        # Auto-detect brands from *_bikes_latest.csv files
        for csv_file in self.data_dir.glob("*_bikes_latest.csv"):
            brand_name = csv_file.stem.replace("_bikes_latest", "").title()
            
            self.logger.info(f"\n🎯 Processing {brand_name}...")
            success = self.update_master_database(brand_name, csv_file)
            
            if success:
                brands_updated.append(brand_name)
        
        # Generate combined summary
        self.generate_combined_summary(brands_updated)
        
        return brands_updated
    
    def generate_combined_summary(self, brands):
        """Generate a combined summary across all brands"""
        summary_file = self.data_dir / "master_database_summary.txt"
        
        with open(summary_file, 'w') as f:
            f.write("🚲 BIKE SCRAPER - MASTER DATABASE SUMMARY\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            total_bikes = 0
            total_available = 0
            total_new = 0
            total_discontinued = 0
            
            for brand in brands:
                files = self.get_brand_files(brand)
                if files['master_csv'].exists():
                    df = pd.read_csv(files['master_csv'])
                    
                    brand_total = len(df)
                    brand_available = len(df[df['status'] == 'Available'])
                    brand_new = len(df[df['status'] == 'New'])
                    brand_discontinued = len(df[df['status'] == 'Discontinued'])
                    
                    f.write(f"🏆 {brand.upper()}:\n")
                    f.write(f"   Total bikes: {brand_total}\n")
                    f.write(f"   Available: {brand_available}\n")
                    f.write(f"   New: {brand_new}\n")
                    f.write(f"   Discontinued: {brand_discontinued}\n\n")
                    
                    total_bikes += brand_total
                    total_available += brand_available
                    total_new += brand_new
                    total_discontinued += brand_discontinued
            
            f.write("📊 TOTAL ACROSS ALL BRANDS:\n")
            f.write(f"   🚲 Total bikes tracked: {total_bikes}\n")
            f.write(f"   ✅ Available: {total_available}\n")
            f.write(f"   🆕 New: {total_new}\n")
            f.write(f"   🔴 Discontinued: {total_discontinued}\n\n")
            
            f.write("📁 FILES GENERATED:\n")
            for brand in brands:
                files = self.get_brand_files(brand)
                f.write(f"   {brand}/ (data/{brand}/):\n")
                f.write(f"     📁 master/: {files['master_csv'].name}, {files['master_json'].name}\n")
                f.write(f"     📁 reports/: {files['discontinued_csv'].name}, {files['available_csv'].name}, {files['new_csv'].name}, {files['status_report'].name}\n")
                f.write(f"     📁 historical/: timestamped archive files\n")
        
        self.logger.info(f"\n🎉 Combined summary saved: {summary_file}")
    
    def safe_csv_export(self, df, file_path):
        """Export DataFrame to CSV with robust handling of problematic characters"""
        def clean_field(value):
            if pd.isna(value):
                return ''
            
            str_value = str(value)
            # Remove problematic characters that can break CSV structure
            str_value = str_value.replace('\n', ' ').replace('\r', ' ')
            str_value = str_value.replace('\t', ' ')  # Replace tabs
            str_value = re.sub(r'\s+', ' ', str_value)  # Normalize whitespace
            str_value = str_value.strip()
            
            return str_value
        
        # Clean all data
        cleaned_df = df.copy()
        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == 'object':
                cleaned_df[col] = cleaned_df[col].apply(clean_field)
        
        # Export with robust settings
        cleaned_df.to_csv(
            file_path,
            index=False,
            encoding='utf-8',
            quoting=csv.QUOTE_ALL,
            escapechar=None,
            doublequote=True
        )
        
        self.logger.info(f"📄 Safely exported CSV to {file_path}")
    
    def organize_existing_files(self, brand_name):
        """Organize existing files in brand folder into new structure"""
        brand_dir = self.data_dir / brand_name
        
        if not brand_dir.exists():
            return
            
        self.logger.info(f"🗂️  Organizing existing files for {brand_name}...")
        
        files = self.get_brand_files(brand_name)  # This creates the new folder structure
        
        # Move master database files
        for old_file in brand_dir.glob("master_*.csv"):
            new_file = files['master_csv'].parent / old_file.name
            if old_file != new_file:
                old_file.rename(new_file)
                self.logger.info(f"   📄 Moved {old_file.name} to master/")
                
        for old_file in brand_dir.glob("master_*.json"):
            new_file = files['master_json'].parent / old_file.name
            if old_file != new_file:
                old_file.rename(new_file)
                self.logger.info(f"   📄 Moved {old_file.name} to master/")
        
        # Move report files
        report_patterns = ["*_available.csv", "*_discontinued.csv", "*_new.csv", "*_status_summary.txt"]
        for pattern in report_patterns:
            for old_file in brand_dir.glob(pattern):
                new_file = files['status_report'].parent / old_file.name
                if old_file != new_file:
                    old_file.rename(new_file)
                    self.logger.info(f"   📄 Moved {old_file.name} to reports/")
        
        # Move historical files (files with timestamps)
        for old_file in brand_dir.glob("*_202*.csv"):
            new_file = files['historical_dir'] / old_file.name
            if old_file != new_file:
                old_file.rename(new_file)
                self.logger.info(f"   📄 Moved {old_file.name} to historical/")
                
        for old_file in brand_dir.glob("*_202*.json"):
            new_file = files['historical_dir'] / old_file.name
            if old_file != new_file:
                old_file.rename(new_file)
                self.logger.info(f"   📄 Moved {old_file.name} to historical/")
                
        for old_file in brand_dir.glob("*_202*.xlsx"):
            new_file = files['historical_dir'] / old_file.name
            if old_file != new_file:
                old_file.rename(new_file)
                self.logger.info(f"   📄 Moved {old_file.name} to historical/")

def main():
    """Main function to run the master database manager"""
    print("🚀 Master Database Manager for Bike Scraper")
    print("=" * 60)
    
    manager = MasterDatabaseManager()
    
    # First, organize existing files into new structure
    print("🗂️  Step 1: Organizing existing files into new folder structure...")
    for csv_file in manager.data_dir.glob("*_bikes_latest.csv"):
        brand_name = csv_file.stem.replace("_bikes_latest", "").title()
        manager.organize_existing_files(brand_name)
    
    print("\n📊 Step 2: Updating master databases...")
    # Update all brands
    updated_brands = manager.update_all_brands()
    
    print(f"\n🎉 Master database update completed!")
    print(f"📊 Brands processed: {', '.join(updated_brands)}")
    print(f"📁 New organized structure created in 'data/' directory")
    print("📁 Structure: data/Brand/master/, data/Brand/reports/, data/Brand/historical/")

if __name__ == "__main__":
    main() 