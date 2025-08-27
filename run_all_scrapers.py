#!/usr/bin/env python3
"""
Run All Scrapers with Master Database Integration
Runs all bike scrapers and automatically updates master databases with discontinued tracking
"""

import subprocess
import sys
import os
from datetime import datetime
from master_database_manager import MasterDatabaseManager

def run_scraper(scraper_name):
    """Run a specific scraper and return success status"""
    print(f"🚀 Running {scraper_name}...")
    try:
        result = subprocess.run([sys.executable, scraper_name], 
                              capture_output=True, text=True, timeout=3600)
        
        if result.returncode == 0:
            print(f"✅ {scraper_name} completed successfully")
            return True
        else:
            print(f"❌ {scraper_name} failed with error:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {scraper_name} timed out after 60 minutes")
        return False
    except Exception as e:
        print(f"💥 Error running {scraper_name}: {e}")
        return False

def main():
    """Main function to run all scrapers and update master databases"""
    print("🚲 BIKE SCRAPER - COMPLETE WORKFLOW")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # List of available scrapers
    scrapers = [
        "canyon_bikes_scraper.py",
        "trek_bikes_scraper.py"
    ]
    
    successful_scrapers = []
    failed_scrapers = []
    
    # Run each scraper
    for scraper in scrapers:
        if os.path.exists(scraper):
            print(f"📍 Step 1: Running {scraper}")
            print("-" * 40)
            
            success = run_scraper(scraper)
            
            if success:
                successful_scrapers.append(scraper)
            else:
                failed_scrapers.append(scraper)
            
            print()
        else:
            print(f"⚠️  Scraper not found: {scraper}")
            failed_scrapers.append(scraper)
    
    # Update master databases if any scrapers succeeded
    if successful_scrapers:
        print("📍 Step 2: Updating Master Databases")
        print("-" * 40)
        
        try:
            manager = MasterDatabaseManager()
            updated_brands = manager.update_all_brands()
            
            print("✅ Master database update completed!")
            print(f"📊 Brands processed: {', '.join(updated_brands)}")
            
        except Exception as e:
            print(f"❌ Master database update failed: {e}")
    
    # Final summary
    print()
    print("🎯 FINAL SUMMARY")
    print("=" * 30)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if successful_scrapers:
        print("✅ Successful scrapers:")
        for scraper in successful_scrapers:
            print(f"   • {scraper}")
    
    if failed_scrapers:
        print()
        print("❌ Failed scrapers:")
        for scraper in failed_scrapers:
            print(f"   • {scraper}")
    
    print()
    print("📁 Generated Files:")
    print("   • Regular scraper outputs: data/*_bikes_latest.*")
    print("   • Brand-specific folders:")
    print("     - data/Canyon/: master_canyon_bikes_all.*, canyon_bikes_discontinued.csv, etc.")
    print("     - data/Trek/: master_trek_bikes_all.*, trek_bikes_discontinued.csv, etc.")
    print("   • Combined summary: data/master_database_summary.txt")
    
    # Return exit code based on scraper success
    if failed_scrapers and not successful_scrapers:
        return 1  # All failed
    elif failed_scrapers:
        return 2  # Some failed
    else:
        return 0  # All succeeded

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 