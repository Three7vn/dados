"""
Web server for Dados UI - serves the web interface and provides real-time data via WebSocket
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import websockets
from websockets.server import WebSocketServerProtocol
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
from urllib.parse import urlparse

class DadosWebServer:
    def __init__(self, host="localhost", http_port=8080, ws_port=8081):
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        self.clients: List[WebSocketServerProtocol] = []
        self.speech_history: List[Dict] = []
        self.action_history: List[Dict] = []
        self.max_history = 50
        
    def add_speech_entry(self, text: str, timestamp: Optional[str] = None):
        """Add a speech input entry"""
        if not timestamp:
            timestamp = time.strftime("[%H:%M:%S]")
        
        entry = {
            "timestamp": timestamp,
            "text": text,
            "type": "speech"
        }
        
        self.speech_history.insert(0, entry)  # Most recent first
        if len(self.speech_history) > self.max_history:
            self.speech_history = self.speech_history[:self.max_history]
            
        # Broadcast to all connected clients (only if event loop is running)
        try:
            asyncio.create_task(self._broadcast_update("speech", entry))
        except RuntimeError:
            # No event loop running yet, skip broadcast
            pass
    
    def add_action_entry(self, action_type: str, details: str, success: bool = True, timestamp: Optional[str] = None):
        """Add an action log entry"""
        if not timestamp:
            timestamp = time.strftime("[%H:%M:%S]")
            
        entry = {
            "timestamp": timestamp,
            "action": action_type,
            "details": details,
            "success": success,
            "type": "action"
        }
        
        self.action_history.insert(0, entry)  # Most recent first
        if len(self.action_history) > self.max_history:
            self.action_history = self.action_history[:self.max_history]
            
        # Broadcast to all connected clients (only if event loop is running)
        try:
            asyncio.create_task(self._broadcast_update("action", entry))
        except RuntimeError:
            # No event loop running yet, skip broadcast
            pass
    
    async def _broadcast_update(self, update_type: str, data: Dict):
        """Broadcast update to all connected WebSocket clients"""
        if not self.clients:
            return
            
        message = json.dumps({
            "type": update_type,
            "data": data
        })
        
        # Send to all clients, remove disconnected ones
        disconnected = []
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client)
        
        for client in disconnected:
            self.clients.remove(client)
    
    async def handle_websocket(self, websocket: WebSocketServerProtocol):
        """Handle WebSocket connections"""
        self.clients.append(websocket)
        print(f"WebSocket client connected: {websocket.remote_address}")
        
        try:
            # Send initial data
            await websocket.send(json.dumps({
                "type": "init",
                "data": {
                    "speech_history": self.speech_history,
                    "action_history": self.action_history
                }
            }))
            
            # Keep connection alive
            async for message in websocket:
                # Handle any client messages if needed
                pass
                
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if websocket in self.clients:
                self.clients.remove(websocket)
            print(f"WebSocket client disconnected: {websocket.remote_address}")
    
    def start_websocket_server(self):
        """Start WebSocket server in background thread"""
        def run_ws():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def start_server():
                server = await websockets.serve(
                    self.handle_websocket,
                    self.host,
                    self.ws_port
                )
                print(f"WebSocket server started on ws://{self.host}:{self.ws_port}")
                await server.wait_closed()
            
            loop.run_until_complete(start_server())
        
        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()
    
    def start_http_server(self):
        """Start HTTP server to serve static files"""
        class DadosHTTPHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                # Serve from the project root directory
                super().__init__(*args, directory=str(Path(__file__).parent.parent), **kwargs)
            
            def end_headers(self):
                # Add CORS headers
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                super().end_headers()
        
        def run_http():
            server = HTTPServer((self.host, self.http_port), DadosHTTPHandler)
            print(f"HTTP server started on http://{self.host}:{self.http_port}")
            server.serve_forever()
        
        http_thread = threading.Thread(target=run_http, daemon=True)
        http_thread.start()
    
    def start(self):
        """Start both HTTP and WebSocket servers"""
        self.start_http_server()
        self.start_websocket_server()
        
        # Add initial system message
        self.add_action_entry("System", "Web server started → Ready for connections", True)

# Global instance for easy access from main.py
web_server = DadosWebServer()
