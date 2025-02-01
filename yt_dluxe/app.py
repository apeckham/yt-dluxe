from flask import Flask, render_template, request, jsonify
import yt_dlp
import threading
import os
import queue
import sys
import logging
from urllib.parse import urlparse
from datetime import datetime
import uuid

# Create a class to hold application state
class DownloadManager:
    def __init__(self, download_dir='.', max_concurrent_downloads=3):
        self.download_dir = os.path.abspath(download_dir)
        self.download_queue = queue.Queue()
        self.active_downloads = {}
        self.download_history = []
        self.active_downloads_lock = threading.Lock()
        self.history_lock = threading.Lock()
        self.max_concurrent_downloads = max_concurrent_downloads
        self.worker_threads = []

    def start_workers(self):
        for _ in range(self.max_concurrent_downloads):
            worker = threading.Thread(target=self._download_worker, daemon=True)
            worker.start()
            self.worker_threads.append(worker)

    def _download_worker(self):
        while True:
            download = self.download_queue.get()
            if download is None:
                break
            
            logging.info("Starting download for %s", download.url)
            try:
                download.status = "downloading"
                with self.active_downloads_lock:
                    self.active_downloads[download.url] = download
                
                ydl_opts = {
                    'format': download.options.get('format', 'best'),
                    'progress_hooks': [lambda d: self._progress_hook(d)],
                    'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
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
                    download.filename = ydl.prepare_filename(info)
                    if "list=" in download.url or "youtube.com/playlist" in download.url:
                        ydl.params['outtmpl'] = os.path.join(self.download_dir, '%(uploader)s', '%(playlist_index)s - %(title)s.%(ext)s')
                        ydl.params['yesplaylist'] = True
                    elif any(x in download.url for x in ['youtube.com/channel', 'youtube.com/user', 'youtube.com/c/']):
                        ydl.params['outtmpl'] = os.path.join(self.download_dir, '%(uploader)s', '%(upload_date)s - %(title)s.%(ext)s')
                        ydl.params['yesplaylist'] = True
                    elif 'entries' in info:
                        ydl.params['outtmpl'] = os.path.join(self.download_dir, '%(uploader)s', '%(playlist_index)s - %(title)s.%(ext)s')
                    ydl.download([download.url])
                    logging.info("Download finished. File saved to %s", download.filename)
                    download.status = "completed"
                
            except Exception as e:
                download.status = "error"
                download.error = str(e)
                if not download.title:  # If title wasn't set, don't show "Initializing..."
                    download.title = "Download Failed"
            
            finally:
                with self.active_downloads_lock:
                    if download.url in self.active_downloads:
                        del self.active_downloads[download.url]
                with self.history_lock:
                    self.download_history.append(download)
                self.download_queue.task_done()

    def _progress_hook(self, d):
        if not isinstance(d, dict):
            return
        status = d.get('status')
        if status == 'downloading':
            info_dict = d.get('info_dict')
            webpage_url = info_dict.get('webpage_url') if isinstance(info_dict, dict) else None
            with self.active_downloads_lock:
                download = None
                if webpage_url:
                    download = self.active_downloads.get(webpage_url)
                if not download:
                    for dl in self.active_downloads.values():
                        if 'filename' in d and dl.url in d['filename']:
                            download = dl
                            break
                if download:
                    total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                    if total_bytes:
                        download.progress = (d.get('downloaded_bytes', 0) / total_bytes) * 100
                    if not download.title and isinstance(info_dict, dict):
                        download.title = info_dict.get('title')
        elif status == 'finished':
            info_dict = d.get('info_dict')
            webpage_url = info_dict.get('webpage_url') if isinstance(info_dict, dict) else None
            with self.active_downloads_lock:
                download = self.active_downloads.get(webpage_url)
                if download:
                    download.status = "completed"
                    download.progress = 100
                    if 'filename' in d:
                        download.filename = d['filename']
                    # Update title to show the saved filename for clarity on file location
                    if download.filename:
                        download.title = os.path.basename(download.filename)

# Create Flask app factory
def create_app(download_manager, server_start_time):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    
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
        download_manager.download_queue.put(download)
        
        return jsonify({
            'message': 'Download added successfully',
            'id': download.id
        })

    @app.route('/status')
    def get_status():
        with download_manager.active_downloads_lock:
            active_downloads_list = [{
                'id': d.id,
                'url': d.url,
                'progress': d.progress,
                'status': d.status,
                'title': d.title,
                'error': d.error,
                'filename': d.filename,
                'timestamp': d.timestamp,
                'active': True
            } for d in download_manager.active_downloads.values()]
        
        with download_manager.history_lock:
            history_list = [{
                'id': d.id,
                'url': d.url,
                'status': d.status,
                'title': d.title,
                'error': d.error,
                'filename': d.filename,
                'timestamp': d.timestamp,
                'active': False
            } for d in download_manager.download_history]
        
        all_downloads = active_downloads_list + history_list
        all_downloads.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({'downloads': all_downloads})

    @app.route('/clear-history', methods=['POST'])
    def clear_history():
        with download_manager.history_lock:
            download_manager.download_history.clear()
        return jsonify({'message': 'History cleared'})

    @app.route('/retry', methods=['POST'])
    def retry_failed_downloads():
        retried = []
        with download_manager.history_lock:
            for download in download_manager.download_history:
                if download.status == "error":
                    download.status = "queued"
                    download.error = None
                    download.timestamp = datetime.now().isoformat()
                    download_manager.download_queue.put(download)
                    retried.append(download.id)
        return jsonify({'message': 'Retried failed downloads', 'retried': retried})
        
    @app.route('/health')
    def health():
        uptime = (datetime.now() - server_start_time).total_seconds()
        return jsonify({'status': 'ok', 'uptime': uptime})

    return app

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

class Download:
    def __init__(self, url, options):
        self.url = url
        self.options = options
        self.progress = 0
        self.status = "queued"
        self.title = None
        self.id = uuid.uuid4().hex
        self.error = None
        self.filename = None
        self.timestamp = datetime.now().isoformat()

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--download-dir', default='.', help='Directory to save downloads (default: current directory)')
    parser.add_argument('--port', type=int, default=5051, help='Port to run the server on (default: 5051)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the server on (default: 0.0.0.0)')
    parser.add_argument('--workers', type=int, default=3, help='Number of concurrent downloads (default: 3)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    download_manager = DownloadManager(
        download_dir=args.download_dir,
        max_concurrent_downloads=args.workers
    )
    os.makedirs(download_manager.download_dir, exist_ok=True)
    download_manager.start_workers()
    
    app = create_app(download_manager, datetime.now())
    try:
        app.run(debug=False, port=args.port, host=args.host)
    finally:
        for _ in range(download_manager.max_concurrent_downloads):
            download_manager.download_queue.put(None)
        for worker in download_manager.worker_threads:
            worker.join()

if __name__ == '__main__':
    main()
