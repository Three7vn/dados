"""
Continuous screen monitoring system that takes screenshots every second
to track screen state changes and cursor position verification.
"""
import threading
import time
import os
from datetime import datetime
from real_time.screenshot import capture_fullscreen

class ScreenMonitor:
    def __init__(self, interval=1.0, data_dir="data/screenshots"):
        self.interval = interval
        self.data_dir = data_dir
        self.running = False
        self.thread = None
        self.screenshot_count = 0
        
        # Ensure screenshot directory exists
        os.makedirs(data_dir, exist_ok=True)
        
    def start(self):
        """Start continuous screenshot monitoring"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"📸 Screen monitoring started (every {self.interval}s)")
        
    def stop(self):
        """Stop continuous screenshot monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("📸 Screen monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop that captures screenshots continuously"""
        while self.running:
            try:
                timestamp = datetime.now().strftime("%H%M%S")
                prefix = f"monitor_{timestamp}_{self.screenshot_count:04d}"
                
                # Capture screenshot
                capture_result = capture_fullscreen(prefix=prefix)
                
                if capture_result:
                    self.screenshot_count += 1
                    # Optional: Log screenshot info
                    if self.screenshot_count % 10 == 0:  # Every 10 screenshots
                        print(f"📸 Captured {self.screenshot_count} monitoring screenshots")
                
            except Exception as e:
                print(f"❌ Screenshot monitoring error: {e}")
                
            time.sleep(self.interval)
            
    def get_latest_screenshot(self):
        """Get the path to the most recent screenshot"""
        try:
            files = [f for f in os.listdir(self.data_dir) if f.startswith("monitor_")]
            if not files:
                return None
                
            # Sort by modification time, get newest
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.data_dir, x)), reverse=True)
            return os.path.join(self.data_dir, files[0])
        except:
            return None
    
    def get_recent_images(self, n: int = 3):
        """Return up to N most recent monitoring screenshot file paths (PNG or WEBP)."""
        try:
            files = [f for f in os.listdir(self.data_dir) if f.startswith("monitor_")]
            if not files:
                return []
            # Sort newest first
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.data_dir, x)), reverse=True)
            paths = [os.path.join(self.data_dir, f) for f in files[:max(0, n)]]
            return paths
        except Exception:
            return []
            
    def verify_cursor_position(self, expected_x, expected_y, tolerance=10):
        """
        Verify cursor is near expected position using latest screenshot
        This would require cursor detection in the screenshot
        """
        # This is a placeholder - would need actual cursor detection
        # Could use image processing to find cursor in screenshot
        latest = self.get_latest_screenshot()
        if not latest:
            return False
            
        # TODO: Implement actual cursor position detection from screenshot
        # For now, return True as placeholder
        return True
        
    def cleanup_old_screenshots(self, keep_last_n=100):
        """Clean up old monitoring screenshots, keeping only the most recent N"""
        try:
            files = [f for f in os.listdir(self.data_dir) if f.startswith("monitor_")]
            if len(files) <= keep_last_n:
                return
                
            # Sort by modification time
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.data_dir, x)))
            
            # Delete oldest files
            to_delete = files[:-keep_last_n]
            for file in to_delete:
                os.remove(os.path.join(self.data_dir, file))
                
            print(f"🧹 Cleaned up {len(to_delete)} old monitoring screenshots")
        except Exception as e:
            print(f"❌ Cleanup error: {e}")
