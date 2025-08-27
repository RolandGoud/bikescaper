#!/usr/bin/env python3
"""
GitHub Sync Script
Syncs all changes to GitHub with organized commit messages
"""

import subprocess
import os
import sys
from datetime import datetime
from pathlib import Path

def run_command(command, description, cwd=None):
    """Run a shell command and handle errors"""
    try:
        print(f"🔄 {description}...")
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True,
            cwd=cwd
        )
        if result.stdout:
            print(f"   ✅ {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error: {e}")
        if e.stderr:
            print(f"   📝 Details: {e.stderr.strip()}")
        return False

def check_git_status():
    """Check if we're in a git repository and show status"""
    if not os.path.exists('.git'):
        print("❌ Not a git repository. Initialize with: git init")
        return False
    
    print("📊 Checking git status...")
    result = subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True)
    
    if not result.stdout.strip():
        print("✅ No changes to commit - repository is up to date")
        return False
    
    print("📝 Changes detected:")
    changes = result.stdout.strip().split('\n')
    for change in changes:
        status = change[:2]
        file_path = change[3:]
        if status.strip() == 'M':
            print(f"   📝 Modified: {file_path}")
        elif status.strip() == 'A':
            print(f"   ➕ Added: {file_path}")
        elif status.strip() == 'D':
            print(f"   ❌ Deleted: {file_path}")
        elif status.strip() == '??':
            print(f"   🆕 Untracked: {file_path}")
        else:
            print(f"   🔄 {status}: {file_path}")
    
    return True

def create_comprehensive_commit_message():
    """Create a detailed commit message for the unified system"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    commit_message = f"""🚀 Implement Unified Master Database System & WordPress Integration

📊 MAJOR FEATURES ADDED:
• Unified master database combining all brands (120 bikes from Trek & Canyon)
• Standardized 66 non-image columns across all brands
• Perfect DD-MM-YYYY date formatting throughout
• Status tracking (Available/Discontinued) with historical data
• Cross-brand analysis capabilities

🔧 NEW SCRIPTS & TOOLS:
• unified_wordpress_converter.py - Multi-brand WordPress export system
• master_database_manager.py - Complete database management
• run_all_scrapers.py - Orchestrated scraping workflow
• Column standardization and reordering system

📊 WORDPRESS INTEGRATION:
• 3 WordPress export formats: individual brands + unified
• 79 custom fields (vs 62 in legacy system)
• Enhanced image support (10 vs 5 images per bike)
• Status tracking fields for availability history
• Automatic filtering of discontinued bikes

🎯 DATA QUALITY IMPROVEMENTS:
• Perfect column parity between brands (189 total columns)
• Consistent date formats across all databases
• Complete specification coverage (66 shared fields)
• Organized folder structure (master/, reports/, historical/)
• Comprehensive archiving system

📁 FILE STRUCTURE:
• data/unified/ - Unified master database (CSV, Excel, JSON)
• data/[Brand]/master/ - Individual brand master databases  
• data/[Brand]/reports/ - Status reports (available, discontinued, new)
• data/wordpress_imports/ - WordPress-ready files
• Comprehensive documentation and instructions

🚀 BENEFITS:
• Single workflow for all brands
• Cross-brand analysis and comparison
• Future-ready for additional brands
• Enhanced WordPress integration
• Complete data preservation and tracking

Generated: {timestamp}"""

    return commit_message

def sync_to_github(commit_message=None, push_to_remote=True):
    """Sync all changes to GitHub"""
    print("🚀 SYNCING TO GITHUB")
    print("=" * 25)
    print()
    
    # Check if we have changes to commit
    if not check_git_status():
        return True
    
    print()
    
    # Add all changes
    if not run_command("git add .", "Adding all changes to staging"):
        return False
    
    # Create commit message if not provided
    if commit_message is None:
        commit_message = create_comprehensive_commit_message()
    
    # Commit changes
    commit_cmd = f'git commit -m "{commit_message}"'
    if not run_command(commit_cmd, "Committing changes"):
        return False
    
    # Push to remote (if requested and remote exists)
    if push_to_remote:
        # Check if we have a remote
        result = subprocess.run('git remote -v', shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            print("\n📡 Pushing to remote repository...")
            if run_command("git push", "Pushing to remote"):
                print("✅ Successfully pushed to GitHub!")
            else:
                print("⚠️  Commit successful, but push failed. You may need to:")
                print("   • Check your internet connection")
                print("   • Verify GitHub authentication") 
                print("   • Run 'git push' manually")
                return False
        else:
            print("ℹ️  No remote repository configured. Commit successful locally.")
            print("   To push to GitHub:")
            print("   • Add remote: git remote add origin <your-repo-url>")
            print("   • Push: git push -u origin main")
    
    return True

def setup_gitignore():
    """Create or update .gitignore file with appropriate exclusions"""
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
*.log
logs/

# Temporary files
*.tmp
*.temp
temp/

# Large data files (optional - uncomment if you want to exclude data)
# data/archive/
# data/*/historical/
# *.xlsx
# *.json

# Sensitive information (if any)
config.ini
.env
secrets.txt
"""
    
    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        print("📝 Creating .gitignore file...")
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        print("✅ .gitignore created")
    else:
        print("ℹ️  .gitignore already exists")

def show_repository_status():
    """Show current repository status and recent commits"""
    print("\n📊 REPOSITORY STATUS:")
    print("=" * 25)
    
    # Show current branch
    result = subprocess.run('git branch --show-current', shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"🌿 Current branch: {result.stdout.strip()}")
    
    # Show recent commits
    result = subprocess.run('git log --oneline -5', shell=True, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout:
        print("\n📜 Recent commits:")
        for line in result.stdout.strip().split('\n'):
            print(f"   • {line}")
    
    # Show remote info
    result = subprocess.run('git remote -v', shell=True, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout:
        print(f"\n📡 Remote repositories:")
        for line in result.stdout.strip().split('\n'):
            print(f"   • {line}")

def main():
    """Main function"""
    print("🔗 GITHUB SYNC FOR UNIFIED BIKE SCRAPER SYSTEM")
    print("=" * 50)
    print()
    
    # Setup gitignore
    setup_gitignore()
    print()
    
    # Sync to GitHub
    success = sync_to_github()
    
    if success:
        print("\n🎉 SYNC COMPLETE!")
        show_repository_status()
        
        print("\n🔧 NEXT STEPS:")
        print("   • Your unified database system is now backed up")
        print("   • All WordPress converters are version controlled")
        print("   • Documentation is preserved in the repository")
        print("   • Ready for collaborative development")
        
    else:
        print("\n❌ SYNC FAILED!")
        print("   Check the errors above and try again")
        sys.exit(1)

if __name__ == "__main__":
    main() 