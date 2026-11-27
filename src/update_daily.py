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
        subprocess.run(
            [sys.executable, script_path], 
            check=True, 
            cwd=os.path.dirname(SRC_DIR)
        )
        print(f"✅ Finished {script_name}\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in {script_name}: {e}\n")
        return False
    except FileNotFoundError:
        print(f"❌ File not found: {script_path}\n")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 BEGINNING DAILY DATA UPDATE PIPELINE")
    print("=" * 60)
    
    scripts = [
        "download_all_prices.py",
        "fundamentals_v2.py",
        "automate_flags.py",
        "snapshot_fundamentals.py",
    ]
    for script_name in scripts:
        if not run_script(script_name):
            sys.exit(1)
    
    print("=" * 60)
    print("🎉 DAILY UPDATE COMPLETE!")
    print("👉 Please restart Streamlit (or clear cache) to see the new data.")
    print("=" * 60)