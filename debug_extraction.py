#!/usr/bin/env python3
"""
Debug script to examine Trek website structure
"""

import requests
from bs4 import BeautifulSoup
import re
import json

def debug_trek_page():
    url = "https://www.trekbikes.com/nl/nl_NL/fietsen/racefietsen/c/B200/?sort=price-asc&pageSize=250&q=%3Arelevance%3AfacetFrameset%3AfacetFrameset2"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    print(f"🔍 Fetching: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"✅ Status: {response.status_code}")
        print(f"✅ Content length: {len(response.content)} bytes")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all script tags
        scripts = soup.find_all('script')
        print(f"✅ Found {len(scripts)} script tags")
        
        # Look for dataLayer
        datalayer_scripts = []
        for i, script in enumerate(scripts):
            if script.string and 'dataLayer' in script.string:
                datalayer_scripts.append((i, script))
                print(f"📊 Script {i} contains dataLayer")
        
        print(f"✅ Found {len(datalayer_scripts)} scripts with dataLayer")
        
        # Examine dataLayer content
        for i, (script_idx, script) in enumerate(datalayer_scripts):
            print(f"\n🔍 Examining dataLayer script {script_idx}:")
            content = script.string
            
            # Look for different patterns
            patterns = [
                (r'dataLayer\.push\(\s*({.*?})\s*\)', 'dataLayer.push'),
                (r'ecommerce["\']?\s*:\s*({.*?})', 'ecommerce object'),
                (r'items["\']?\s*:\s*(\[.*?\])', 'items array'),
                (r'products["\']?\s*:\s*(\[.*?\])', 'products array'),
                (r'"item_name"["\']?\s*:\s*"([^"]*)"', 'item names'),
                (r'"name"["\']?\s*:\s*"([^"]*)"', 'names'),
            ]
            
            for pattern, description in patterns:
                matches = re.findall(pattern, content, re.DOTALL)
                if matches:
                    print(f"  ✅ Found {len(matches)} matches for {description}")
                    if description in ['item names', 'names']:
                        print(f"     First few: {matches[:3]}")
                    else:
                        print(f"     First match preview: {str(matches[0])[:100]}...")
                else:
                    print(f"  ❌ No matches for {description}")
            
            # Show a sample of the content
            if len(content) > 1000:
                print(f"  📝 Script content sample (first 500 chars):")
                print(f"     {content[:500]}...")
            else:
                print(f"  📝 Full script content:")
                print(f"     {content}")
        
        # Look for bike-related content in HTML
        print(f"\n🔍 Looking for bike content in HTML:")
        
        # Look for product tiles or cards
        product_selectors = [
            '.product-tile',
            '.product-card',
            '.product-item',
            '[data-testid*="product"]',
            '.tile',
            '.card'
        ]
        
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"  ✅ Found {len(elements)} elements with selector: {selector}")
                if elements:
                    first_elem = elements[0]
                    print(f"     First element text: {first_elem.get_text()[:100]}...")
            else:
                print(f"  ❌ No elements found for selector: {selector}")
        
        # Look for bike names in the HTML
        text_content = soup.get_text()
        bike_keywords = ['Domane', 'Madone', 'Émonda', 'Checkpoint', 'Speed Concept', 'Boone', 'FX']
        
        print(f"\n🔍 Looking for bike names in page text:")
        for keyword in bike_keywords:
            if keyword in text_content:
                print(f"  ✅ Found '{keyword}' in page text")
            else:
                print(f"  ❌ '{keyword}' not found in page text")
        
        # Save debug HTML
        with open('debug_trek_page.html', 'w', encoding='utf-8') as f:
            f.write(str(soup))
        print(f"\n💾 Saved debug HTML to debug_trek_page.html")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_trek_page() 