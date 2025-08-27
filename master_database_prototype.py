#!/usr/bin/env python3
"""
Master Database Prototype for Bike Scraper
Tracks all bikes over time with clear discontinued status indicators
"""

import pandas as pd
import json
from datetime import datetime
import os
from pathlib import Path

class MasterBikeDatabase:
    def __init__(self, brand_name):
        self.brand_name = brand_name
        self.master_file = f"data/master_{brand_name.lower()}_bikes_all.csv"
        self.master_json = f"data/master_{brand_name.lower()}_bikes_all.json"
        
    def load_master_database(self):
        """Load existing master database or create new one"""
        if os.path.exists(self.master_file):
            print(f"📖 Loading existing master database: {self.master_file}")
            return pd.read_csv(self.master_file)
        else:
            print(f"🆕 Creating new master database: {self.master_file}")
            return pd.DataFrame(columns=[
                'name', 'brand', 'price', 'currency', 'url', 'image_url',
                'status', 'first_seen_date', 'last_seen_date', 'last_updated',
                'spec_FrameFit', 'spec_Frame', 'spec_Gewichtslimiet',
                'spec_Shifter', 'spec_Stuur', 'description'
            ])
    
    def determine_bike_status(self, bike_name, current_bikes, master_df):
        """Determine if bike is New, Available, or Discontinued"""
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Check if bike exists in master database
        existing_bike = master_df[master_df['name'] == bike_name]
        
        if bike_name in current_bikes:
            if existing_bike.empty:
                return 'New', current_date, current_date
            else:
                # Bike was already in database and still available
                first_seen = existing_bike.iloc[0]['first_seen_date']
                return 'Available', first_seen, current_date
        else:
            # Bike not in current scrape
            if not existing_bike.empty:
                # Bike exists in master but not in current = Discontinued
                first_seen = existing_bike.iloc[0]['first_seen_date']
                last_seen = existing_bike.iloc[0]['last_seen_date']
                return 'Discontinued', first_seen, last_seen
            else:
                # This shouldn't happen in normal flow
                return 'Unknown', current_date, current_date
    
    def update_master_database(self, current_data_file):
        """Update master database with current scrape data"""
        print(f"🔄 Updating master database for {self.brand_name}...")
        
        # Load current scrape data
        current_df = pd.read_csv(current_data_file)
        current_bikes = set(current_df['name'].tolist())
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Load master database
        master_df = self.load_master_database()
        
        # Get all bikes that have ever existed
        all_known_bikes = set(master_df['name'].tolist()) if not master_df.empty else set()
        all_bikes = current_bikes.union(all_known_bikes)
        
        print(f"📊 Analysis:")
        print(f"   Current bikes: {len(current_bikes)}")
        print(f"   Previously known bikes: {len(all_known_bikes)}")
        print(f"   Total unique bikes ever: {len(all_bikes)}")
        
        # Process each bike
        updated_records = []
        new_count = 0
        discontinued_count = 0
        available_count = 0
        
        for bike_name in all_bikes:
            status, first_seen, last_seen = self.determine_bike_status(
                bike_name, current_bikes, master_df
            )
            
            # Get bike data from current scrape if available
            if bike_name in current_bikes:
                current_bike_data = current_df[current_df['name'] == bike_name].iloc[0]
                
                # Start with ALL data from current scrape
                bike_record = current_bike_data.to_dict()
                
                # Add/update master database specific fields
                bike_record['status'] = status
                bike_record['first_seen_date'] = first_seen
                bike_record['last_seen_date'] = last_seen
                bike_record['last_updated'] = current_date
                
                # Ensure brand is set if missing
                if 'brand' not in bike_record or not bike_record['brand']:
                    bike_record['brand'] = self.brand_name
            else:
                # Bike is discontinued, preserve existing data
                existing_bike = master_df[master_df['name'] == bike_name].iloc[0]
                bike_record = existing_bike.to_dict()
                bike_record['status'] = 'Discontinued'
                bike_record['last_updated'] = current_date
            
            updated_records.append(bike_record)
            
            # Count status types
            if status == 'New':
                new_count += 1
            elif status == 'Discontinued':
                discontinued_count += 1
            elif status == 'Available':
                available_count += 1
        
        # Create updated master dataframe
        updated_master_df = pd.DataFrame(updated_records)
        
        # Sort by status (Available first, then New, then Discontinued) and name
        status_order = {'Available': 1, 'New': 2, 'Discontinued': 3}
        updated_master_df['status_order'] = updated_master_df['status'].map(status_order)
        updated_master_df = updated_master_df.sort_values(['status_order', 'name']).drop('status_order', axis=1)
        
        # Save updated master database
        updated_master_df.to_csv(self.master_file, index=False)
        updated_master_df.to_json(self.master_json, orient='records', indent=2)
        
        print(f"✅ Master database updated!")
        print(f"   📈 New bikes: {new_count}")
        print(f"   ✅ Available bikes: {available_count}")
        print(f"   🔴 Discontinued bikes: {discontinued_count}")
        print(f"   📁 Saved to: {self.master_file}")
        
        return updated_master_df, {
            'new': new_count,
            'available': available_count,
            'discontinued': discontinued_count
        }
    
    def generate_status_reports(self, master_df):
        """Generate detailed status reports"""
        
        # Create status-specific exports
        available_bikes = master_df[master_df['status'] == 'Available']
        new_bikes = master_df[master_df['status'] == 'New']
        discontinued_bikes = master_df[master_df['status'] == 'Discontinued']
        
        # Save status-specific files
        available_file = f"data/{self.brand_name.lower()}_bikes_available.csv"
        new_file = f"data/{self.brand_name.lower()}_bikes_new.csv"
        discontinued_file = f"data/{self.brand_name.lower()}_bikes_discontinued.csv"
        
        available_bikes.to_csv(available_file, index=False)
        new_bikes.to_csv(new_file, index=False)
        discontinued_bikes.to_csv(discontinued_file, index=False)
        
        print(f"\n📋 Status Reports Generated:")
        print(f"   ✅ Available models: {available_file} ({len(available_bikes)} bikes)")
        print(f"   🆕 New models: {new_file} ({len(new_bikes)} bikes)")
        print(f"   🔴 Discontinued models: {discontinued_file} ({len(discontinued_bikes)} bikes)")
        
        # Generate summary report
        summary_file = f"data/{self.brand_name.lower()}_status_summary.txt"
        with open(summary_file, 'w') as f:
            f.write(f"{self.brand_name} Bikes Status Summary\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"📊 OVERVIEW:\n")
            f.write(f"Total bikes tracked: {len(master_df)}\n")
            f.write(f"Available: {len(available_bikes)}\n")
            f.write(f"New: {len(new_bikes)}\n")
            f.write(f"Discontinued: {len(discontinued_bikes)}\n\n")
            
            if len(new_bikes) > 0:
                f.write(f"🆕 NEW BIKES ({len(new_bikes)}):\n")
                for _, bike in new_bikes.iterrows():
                    f.write(f"   • {bike['name']} (€{bike['price']}) - Added {bike['first_seen_date']}\n")
                f.write("\n")
            
            if len(discontinued_bikes) > 0:
                f.write(f"🔴 DISCONTINUED BIKES ({len(discontinued_bikes)}):\n")
                for _, bike in discontinued_bikes.iterrows():
                    f.write(f"   ❌ {bike['name']} - Last seen {bike['last_seen_date']}\n")
                f.write("\n")
        
        print(f"   📄 Summary report: {summary_file}")
        
        return {
            'available_file': available_file,
            'new_file': new_file,
            'discontinued_file': discontinued_file,
            'summary_file': summary_file
        }

def main():
    """Demo the master database functionality"""
    print("🚀 Master Database Prototype for Bike Tracking")
    print("=" * 60)
    
    # Test with Canyon bikes
    canyon_db = MasterBikeDatabase("Canyon")
    
    print(f"\n🎯 Testing with Canyon bikes...")
    current_data_file = "data/canyon_bikes_latest.csv"
    
    if os.path.exists(current_data_file):
        master_df, stats = canyon_db.update_master_database(current_data_file)
        reports = canyon_db.generate_status_reports(master_df)
        
        print(f"\n🎉 Prototype completed successfully!")
        print(f"📁 Master database: {canyon_db.master_file}")
        
        # Show discontinued bikes clearly
        discontinued_bikes = master_df[master_df['status'] == 'Discontinued']
        if len(discontinued_bikes) > 0:
            print(f"\n🔴 DISCONTINUED BIKES CLEARLY MARKED:")
            for _, bike in discontinued_bikes.iterrows():
                print(f"   ❌ {bike['name']} - Last available: {bike['last_seen_date']}")
    else:
        print(f"❌ Current data file not found: {current_data_file}")
        print("   Run the Canyon scraper first to generate current data.")

if __name__ == "__main__":
    main() 