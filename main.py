import os
import sys
import time
import requests

print("=== Replit Automation Script ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print("Script is running successfully!")

# Example: Download a file from the internet
url = "https://httpbin.org/get"
try:
    response = requests.get(url, timeout=10)
    print(f"\nDownload test: Status {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")

print("\nScript complete. You can now add your own code.")
