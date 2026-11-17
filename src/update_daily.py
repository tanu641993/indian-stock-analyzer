# src/update_daily.py

import subprocess
import sys
import datetime
import os

# Get the absolute path of the 'src' folder where this script lives
SRC_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script(script_name):
    """Runs a Python script from the src folder and handles errors"""
    script_path = os.path.join(SRC_DIR, script_name)
    
    print(f"⏳ Starting {script_name} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    try:
        # Run the script using the same Python executable (conda environment)
        result = subprocess.run(
            [sys.executable, script_path], 
            check=True, 
            cwd=os.path.dirname(SRC_DIR) # Run from the project root
        )
        print(f"✅ Finished {script_name}\n")
    except subprocess.CalledProcessError as e:
        # If the script fails (e.g., network error, database lock), catch it and continue
        print(f"❌ Error in {script_name}: {e}\n")
    except FileNotFoundError:
        print(f"❌ File not found: {script_path}\n")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 BEGINNING DAILY DATA UPDATE PIPELINE")
    print("=" * 60)
    
    # Step 1: Update historical prices
    run_script("download_all_prices.py")
    
    # Step 2: Update fundamental data (ROE, ROCE, CAGR, etc.)
    run_script("fundamentals.py")
    
    # Step 3: Automatically calculate Market Leaders & Auditor Red Flags
    run_script("automate_flags.py")
    
    print("=" * 60)
    print("🎉 DAILY UPDATE COMPLETE!")
    print("👉 Please restart Streamlit (or clear cache) to see the new data.")
    print("=" * 60)