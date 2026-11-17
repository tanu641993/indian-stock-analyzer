# src/update_daily.py

import subprocess
import sys
import datetime
import os

SRC_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script(script_name):
    script_path = os.path.join(SRC_DIR, script_name)
    
    print(f"⏳ Starting {script_name} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    try:
        result = subprocess.run(
            [sys.executable, script_path], 
            check=True, 
            cwd=os.path.dirname(SRC_DIR)
        )
        print(f"✅ Finished {script_name}\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in {script_name}: {e}\n")
    except FileNotFoundError:
        print(f"❌ File not found: {script_path}\n")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 BEGINNING DAILY DATA UPDATE PIPELINE")
    print("=" * 60)
    
    # Step 1: Update historical prices
    #run_script("download_all_prices.py")
    
    # Step 2: Update deep fundamental data (5Y CAGR, FCF, ROCE trends, Market Cap)
    run_script("fundamentals_v2.py")
    
    # Step 3: Automatically calculate Market Leaders & Auditor Red Flags
    run_script("automate_flags.py")
    
    print("=" * 60)
    print("🎉 DAILY UPDATE COMPLETE!")
    print("👉 Please restart Streamlit (or clear cache) to see the new data.")
    print("=" * 60)