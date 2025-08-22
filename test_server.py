#!/usr/bin/env python3
"""
Simple test script to verify Django server can start
"""
import subprocess
import time
import requests
import sys

def test_server():
    print("Starting Django development server...")
    
    # Start the server in background
    server = subprocess.Popen([
        'python3', 'manage.py', 'runserver', '127.0.0.1:8000'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait a moment for server to start
    time.sleep(3)
    
    try:
        # Test if server is responding
        response = requests.get('http://127.0.0.1:8000/admin/', timeout=5)
        if response.status_code == 200:
            print("✅ Server is running successfully!")
            print("✅ Admin interface is accessible at http://127.0.0.1:8000/admin/")
            print("✅ API endpoints are available at http://127.0.0.1:8000/api/")
            return True
        else:
            print(f"❌ Server responded with status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to server: {e}")
        return False
    finally:
        # Stop the server
        server.terminate()
        server.wait()

if __name__ == '__main__':
    success = test_server()
    sys.exit(0 if success else 1)