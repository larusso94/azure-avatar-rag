#!/usr/bin/env python3
"""
Simple HTTP Server for Azure Avatar Demo
Serves the static files for the Talking Avatar application
"""

import http.server
import socketserver
import os
import sys
import time
import subprocess
import socket
from pathlib import Path

# Configuration - Fixed port for frontend (backend uses 5000)
PORT = 8080
DIRECTORY = Path(__file__).parent

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP Request Handler with CORS support"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)
    
    def end_headers(self):
        """Add CORS headers to response"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def log_message(self, format, *args):
        """Override to customize logging - suppress broken pipe errors"""
        # Only log if not a broken pipe or connection reset
        if "Broken pipe" not in str(args) and "Connection reset" not in str(args):
            super().log_message(format, *args)
    
    def handle_one_request(self):
        """Handle a single HTTP request - with error suppression"""
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected - this is normal, don't log
            pass
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        # Custom log format
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

def is_port_in_use(port):
    """Check if port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True

def kill_port_process(port, max_retries=3, retry_delay=2):
    """Kill process using the specified port with retry logic."""
    import os
    current_pid = os.getpid()
    
    for attempt in range(max_retries):
        if not is_port_in_use(port):
            return True
        
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries}: Killing process on port {port}...")
            
            # Get PIDs using the port
            result = subprocess.run(
                f"lsof -ti:{port}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid_str in pids:
                    try:
                        pid = int(pid_str.strip())
                        # Don't kill ourselves
                        if pid != current_pid:
                            os.kill(pid, 9)
                            print(f"✅ Killed process {pid}")
                    except (ValueError, ProcessLookupError, PermissionError) as e:
                        print(f"⚠️  Could not kill process {pid_str}: {e}")
            
            # Wait for port to be released
            time.sleep(retry_delay)
            
            if not is_port_in_use(port):
                print(f"✅ Port {port} is now available")
                return True
            else:
                print(f"⚠️  Port {port} still in use, trying again...")
                
        except subprocess.TimeoutExpired:
            print(f"⚠️  Timeout killing process on port {port}")
        except Exception as e:
            print(f"⚠️  Error killing process: {e}")
    
    return False

def main():
    """Start the HTTP server"""
    os.chdir(DIRECTORY)
    
    # Check port availability with automatic retry
    if is_port_in_use(PORT):
        print("="*60)
        print(f"⚠️  WARNING: Port {PORT} is already in use!")
        print(f"🔧 Attempting to free port automatically...")
        print("="*60)
        
        if not kill_port_process(PORT, max_retries=3, retry_delay=2):
            print("="*60)
            print(f"❌ ERROR: Could not free port {PORT} after 3 attempts!")
            print(f"")
            print(f"Manual intervention required:")
            print(f"  lsof -ti:{PORT} | xargs kill -9")
            print(f"")
            print(f"Or find the process:")
            print(f"  lsof -i:{PORT}")
            print("="*60)
            sys.exit(1)
    
    # Try to start server on fixed port
    try:
        httpd = socketserver.TCPServer(("", PORT), CORSRequestHandler)
        
        print(f"=" * 60)
        print(f"🚀 Azure Avatar Server Running")
        print(f"=" * 60)
        print(f"📂 Serving directory: {DIRECTORY}")
        print(f"🌐 Server URL: http://localhost:{PORT}")
        print(f"📄 Open in browser: http://localhost:{PORT}/index.html")
        print(f"🔗 Backend API: http://localhost:5001")
        print(f"=" * 60)
        print(f"Press Ctrl+C to stop the server")
        print(f"=" * 60)
        
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        httpd.shutdown()
        sys.exit(0)

if __name__ == "__main__":
    main()
