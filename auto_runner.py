import schedule
import time
import subprocess
import os
from datetime import datetime

def run_trader():
    print(f"\n⏰ AUTO RUNNER: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🤖 Running AI Trader automatically...")
    subprocess.run(['python', 'live_trader.py'])
    print("✅ Done! Next run tomorrow.")

def run_dashboard():
    subprocess.Popen(['streamlit', 'run', 'dashboard_v2.py'])
    print("📊 Dashboard started!")

print("🤖 AUTO DAILY RUNNER STARTED!")
print("=" * 50)
print("📅 Schedule:")
print("   9:00 AM  → Indian market open")
print("   3:30 PM  → Indian market close")
print("   9:30 PM  → US market check")
print("=" * 50)

# Schedule trading times
schedule.every().day.at("09:00").do(run_trader)
schedule.every().day.at("15:30").do(run_trader)
schedule.every().day.at("21:30").do(run_trader)

# Start dashboard immediately
run_dashboard()

print("✅ Auto runner is active!")
print("🔄 System will trade automatically at scheduled times!")
print("Press Ctrl+C to stop\n")

while True:
    schedule.run_pending()
    time.sleep(30)
