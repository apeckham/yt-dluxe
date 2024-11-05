from flask import Flask, render_template, request, jsonify
import yt_dlp
import threading
import os
import queue
import sys
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Global variables
download_queue = queue.Queue()
active_downloads = {}
download_history = []
DOWNLOAD_DIR = '.'  # Default to current directory
active_downloads_lock = threading.Lock()
history_lock = threading.Lock()
MAX_CONCURRENT_DOWNLOADS = 3  # Adjust this number as needed
worker_threads = []

class Download:
    def __init__(self, url, options):
        self.url = url
        self.options = options
        self.progress = 0
        self.status = "queued"
        self.title = None
        self.id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.error = None
        self.timestamp = datetime.now().isoformat()

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def my_hook(d):
    if d['status'] == 'downloading':
        with active_downloads_lock:
            download = active_downloads.get(d.get('info_dict', {}).get('webpage_url'))
            if download:
                # Calculate download progress
                if 'total_bytes' in d:
                    download.progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                elif 'total_bytes_estimate' in d:
                    download.progress = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                if not download.title:  # Only set title if not set yet
                    download.title = d.get('info_dict', {}).get('title')
    elif d['status'] == 'finished':
        with active_downloads_lock:
            download = active_downloads.get(d.get('info_dict', {}).get('webpage_url'))
            if download:
                download.status = "processing"
                download.progress = 100

def download_worker():
    while True:
        download = download_queue.get()
        if download is None:
            break
        
        try:
            download.status = "downloading"
            with active_downloads_lock:
                active_downloads[download.url] = download
            
            ydl_opts = {
                'format': download.options.get('format', 'best'),
                'progress_hooks': [my_hook],
                'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            }
            
            # Add audio extraction if selected
            if download.options.get('extract_audio'):
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': download.options.get('audio_format', 'mp3'),
                    }]
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(download.url, download=False)
                download.title = info.get('title')  # Set title before download starts
                ydl.download([download.url])
            
            download.status = "completed"
            
        except Exception as e:
            download.status = "error"
            download.error = str(e)
            if not download.title:  # If title wasn't set, don't show "Initializing..."
                download.title = "Download Failed"
        
        finally:
            with active_downloads_lock:
                if download.url in active_downloads:
                    del active_downloads[download.url]
            with history_lock:
                download_history.append(download)
            download_queue.task_done()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_download():
    url = request.form.get('url')
    
    if not validate_url(url):
        return jsonify({'error': 'Invalid URL'}), 400
    
    options = {
        'format': request.form.get('format', 'best'),
        'extract_audio': request.form.get('extract_audio') == 'true',
        'audio_format': request.form.get('audio_format', 'mp3')
    }
    
    download = Download(url, options)
    download_queue.put(download)
    
    return jsonify({
        'message': 'Download added successfully',
        'id': download.id
    })

@app.route('/status')
def get_status():
    with active_downloads_lock:
        active_downloads_list = [{
            'id': d.id,
            'url': d.url,
            'progress': d.progress,
            'status': d.status,
            'title': d.title,
            'error': d.error,
            'timestamp': d.timestamp,
            'active': True
        } for d in active_downloads.values()]
    
    with history_lock:
        history_list = [{
            'id': d.id,
            'url': d.url,
            'status': d.status,
            'title': d.title,
            'error': d.error,
            'timestamp': d.timestamp,
            'active': False
        } for d in download_history]
    
    all_downloads = active_downloads_list + history_list
    all_downloads.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({'downloads': all_downloads})

@app.route('/clear-history', methods=['POST'])
def clear_history():
    with history_lock:
        download_history.clear()
    return jsonify({'message': 'History cleared'})

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--download-dir', default='.', help='Directory to save downloads (default: current directory)')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to run the server on (default: localhost)')
    parser.add_argument('--workers', type=int, default=3, help='Number of concurrent downloads (default: 3)')
    args = parser.parse_args()

    global DOWNLOAD_DIR, MAX_CONCURRENT_DOWNLOADS
    DOWNLOAD_DIR = os.path.abspath(args.download_dir)
    MAX_CONCURRENT_DOWNLOADS = args.workers
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Start multiple download worker threads
    for _ in range(MAX_CONCURRENT_DOWNLOADS):
        worker = threading.Thread(target=download_worker, daemon=True)
        worker.start()
        worker_threads.append(worker)
    
    debug_mode = False
    app.run(debug=debug_mode, port=args.port, host=args.host)

if __name__ == '__main__':
    main()