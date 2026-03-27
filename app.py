from flask import Flask, send_file, jsonify, request
from flask_cors import CORS
import aiohttp
import asyncio
import os
import io
from bs4 import BeautifulSoup
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Your authentication cookies (get these once from your browser)
# IMPORTANT: You need to be logged into kernelos.org with an account that's in the required Discord server
COOKIES = {
    # Add your cookies here after logging into kernelos.org
    # Go to https://kernelos.org/games/, login with Discord
    # Open DevTools (F12) → Application → Cookies → https://kernelos.org
    # Copy all cookie values below
    'session': 'YOUR_SESSION_COOKIE_HERE',
    # Add any other cookies like 'token', 'discord_token', etc.
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://kernelos.org/games/'
}

class ManifestFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.cookies.update(COOKIES)
    
    def get_manifest(self, game_id):
        """Fetch manifest for given game ID"""
        try:
            # Step 1: Get the main page
            response = self.session.get('https://kernelos.org/games/')
            if response.status_code != 200:
                return None, f"Failed to access site: {response.status_code}"
            
            # Step 2: Submit the game ID
            data = {
                'appid': game_id,
                'submit': 'Generate'
            }
            
            post_response = self.session.post('https://kernelos.org/games/', data=data)
            
            if post_response.status_code != 200:
                return None, f"Failed to submit: {post_response.status_code}"
            
            # Step 3: Parse the response for download link
            soup = BeautifulSoup(post_response.text, 'html.parser')
            
            # Look for download links
            download_url = None
            file_type = None
            
            # Check for ZIP first
            zip_link = soup.find('a', href=lambda x: x and x.endswith('.zip') and game_id in x)
            if zip_link:
                download_url = zip_link['href']
                file_type = 'zip'
            else:
                # Check for LUA file
                lua_link = soup.find('a', href=lambda x: x and x.endswith('.lua') and game_id in x)
                if lua_link:
                    download_url = lua_link['href']
                    file_type = 'lua'
            
            if not download_url:
                # Try to find any link with the game ID
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    if game_id in link['href'] and ('.lua' in link['href'] or '.zip' in link['href']):
                        download_url = link['href']
                        file_type = 'zip' if '.zip' in link['href'] else 'lua'
                        break
            
            if not download_url:
                return None, "No download link found. Make sure the game ID exists and you're authenticated."
            
            # Make sure URL is absolute
            if download_url.startswith('/'):
                download_url = f"https://kernelos.org{download_url}"
            
            # Step 4: Download the actual file
            file_response = self.session.get(download_url)
            
            if file_response.status_code == 200:
                filename = f"{game_id}.{file_type}"
                return file_response.content, filename
            else:
                return None, f"Failed to download file: {file_response.status_code}"
                
        except Exception as e:
            return None, f"Error: {str(e)}"

fetcher = ManifestFetcher()

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/download/<game_id>')
def download_manifest(game_id):
    """Endpoint to download manifest for a game ID"""
    try:
        # Validate game ID
        if not game_id or not game_id.isdigit():
            return jsonify({'error': 'Invalid game ID. Must be numbers only.'}), 400
        
        # Fetch the manifest
        file_content, filename_or_error = fetcher.get_manifest(game_id)
        
        if file_content:
            # Send file to user
            return send_file(
                io.BytesIO(file_content),
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name=filename_or_error
            )
        else:
            return jsonify({'error': filename_or_error}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/check_status')
def check_status():
    """Check if authentication is working"""
    try:
        response = fetcher.session.get('https://kernelos.org/games/')
        if response.status_code == 200:
            # Check if we're logged in by looking for logout button or user info
            if 'logout' in response.text.lower() or 'discord' in response.text.lower():
                return jsonify({'status': 'authenticated'})
        return jsonify({'status': 'needs_auth', 'message': 'Please update cookies'})
    except:
        return jsonify({'status': 'error', 'message': 'Cannot connect to kernelos.org'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
