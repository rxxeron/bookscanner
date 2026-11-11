#!/usr/bin/env python3
"""
Local Wi-Fi Book Scanner Server (Dual HTTP/HTTPS)
Supports:
  - HTTPS (Port 5001): Direct embedded in-browser live camera viewfinder (stays on same page, zero app switching)
  - HTTP (Port 5000): Standard web access and quick fallback
  - Fast client-side sharpness analysis and rapid compression (<0.2s per page)
"""

import os
import sys
import json
import ssl
import socket
import urllib.parse
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import io
import subprocess
import base64
import requests
from pathlib import Path
from PIL import Image, ImageFilter, ImageStat, ImageOps

HTTP_PORT = int(os.environ.get("PORT", 5000))
HTTPS_PORT = 5001
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
CERT_FILE = BASE_DIR / "cert.pem"
KEY_FILE = BASE_DIR / "key.pem"

# Google Drive Webhook Integration (via Google Apps Script or Cloud endpoint)
DEFAULT_WEBHOOK = "https://script.google.com/macros/s/AKfycby8Klzd5e0vimyKh61uC3URsGvgIkQR3hukjIId_WosyGuoqWj4cW4bB3VPVeIG6iIb/exec"
GDRIVE_WEBHOOK_URL = os.environ.get("GDRIVE_WEBHOOK_URL", "").strip()
GDRIVE_CONFIG_FILE = BASE_DIR / "config.json"
if not GDRIVE_WEBHOOK_URL and GDRIVE_CONFIG_FILE.exists():
    try:
        _cfg = json.loads(GDRIVE_CONFIG_FILE.read_text(encoding='utf-8'))
        GDRIVE_WEBHOOK_URL = _cfg.get("gdrive_webhook_url", "").strip()
    except Exception:
        pass
if not GDRIVE_WEBHOOK_URL:
    GDRIVE_WEBHOOK_URL = DEFAULT_WEBHOOK

# Dedicated Mother Folder inside Prep404
# Automatically resolves Prep404 / BookScans relative to this script or defaults to Prep404 directory
_cur = BASE_DIR
_prep404_dir = None
while _cur.name and _cur.parent != _cur:
    if _cur.name.lower() == "prep404":
        _prep404_dir = _cur
        break
    _cur = _cur.parent

if _prep404_dir:
    MOTHER_DIR = _prep404_dir / "BookScans"
elif Path("D:/Prep404/BookScans").exists() or Path("D:/Prep404").exists():
    MOTHER_DIR = Path("D:/Prep404/BookScans")
elif Path("E:/01_Development_Projects/Prep404/BookScans").exists() or Path("E:/01_Development_Projects/Prep404").exists():
    MOTHER_DIR = Path("E:/01_Development_Projects/Prep404/BookScans")
else:
    MOTHER_DIR = BASE_DIR.parent / "BookScans"

try:
    MOTHER_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    MOTHER_DIR = BASE_DIR / "scanned_books"
    MOTHER_DIR.mkdir(parents=True, exist_ok=True)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Thread lock to guarantee safe page numbering when multiple phones scan at the same time
save_lock = threading.Lock()

def ensure_ssl_certificates():
    """Ensure self-signed SSL certificates exist for embedded camera access."""
    if CERT_FILE.exists() and KEY_FILE.exists():
        return True

    openssl_bins = [
        "openssl",
        r"C:\Program Files\Git\usr\bin\openssl.exe",
        r"C:\Program Files (x86)\Git\usr\bin\openssl.exe"
    ]
    openssl_cmd = None
    for b in openssl_bins:
        try:
            res = subprocess.run([b, "version"], capture_output=True, text=True)
            if res.returncode == 0:
                openssl_cmd = b
                break
        except Exception:
            continue

    if openssl_cmd:
        try:
            local_ip = get_local_ip()
            subprocess.run([
                openssl_cmd, "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", str(KEY_FILE),
                "-out", str(CERT_FILE),
                "-days", "3650", "-nodes",
                "-subj", f"/CN={local_ip}",
                "-addext", f"subjectAltName=IP:{local_ip},IP:127.0.0.1,DNS:localhost"
            ], check=True, capture_output=True)
            return True
        except Exception as e:
            print(f"Warning: Failed to generate SSL cert: {e}")
            return False
    return False

def get_local_ip():
    """Detect local Wi-Fi / LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def upload_to_gdrive(subject, book, filename, file_bytes, mime_type="image/jpeg"):
    """Uploads file to Google Drive asynchronously via Webhook (Google Apps Script)."""
    if not GDRIVE_WEBHOOK_URL:
        return None
    try:
        b64_data = base64.b64encode(file_bytes).decode('ascii')
        payload = {
            "subject": subject,
            "book": book,
            "filename": filename,
            "mime_type": mime_type,
            "image_base64": b64_data
        }
        res = requests.post(GDRIVE_WEBHOOK_URL, json=payload, timeout=60)
        if res.status_code == 200:
            try:
                data = res.json()
                if data.get("success"):
                    print(f"[Google Drive] Synced {subject}/{book}/{filename} -> {data.get('file_url', 'OK')}")
                    return data
                else:
                    print(f"[Google Drive Error] {data.get('error')}")
            except Exception:
                print(f"[Google Drive] Upload response: {res.text[:120]}")
        else:
            print(f"[Google Drive HTTP Error] Status code {res.status_code}")
    except Exception as e:
        print(f"[Google Drive Upload Exception] {e}")
    return None

def upload_to_gdrive_async(subject, book, filename, file_bytes, mime_type="image/jpeg"):
    """Fire-and-forget background upload so UI remains ultra-fast (~0.05s response)."""
    t = threading.Thread(
        target=upload_to_gdrive,
        args=(subject, book, filename, file_bytes, mime_type),
        daemon=True
    )
    t.start()

def calculate_sharpness(pil_img):
    """Fast Laplacian variance sharpness check."""
    gray = pil_img.convert('L')
    w, h = gray.size
    max_dim = 1600
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        gray = gray.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)

    kernel = ImageFilter.Kernel(
        (3, 3),
        [0, 1, 0,
         1, -4, 1,
         0, 1, 0],
        scale=1,
        offset=128
    )
    edges = gray.filter(kernel)
    stat = ImageStat.Stat(edges)
    return round(float(stat.var[0]), 1)

def sanitize_folder_segment(name, default="General"):
    """Sanitize subject/book subfolder names for Windows paths."""
    if not name or not name.strip():
        return default
    invalid = '<>:"/\\|?*'
    safe = "".join(c if c not in invalid else "_" for c in name.strip())
    safe = safe.strip(". ")
    return safe or default

def resolve_book_dir(subject, book):
    """Resolve subfolder inside MOTHER_DIR safely."""
    safe_sub = sanitize_folder_segment(subject, "General")
    safe_bk = sanitize_folder_segment(book, "Book_Scans")
    target = (MOTHER_DIR / safe_sub / safe_bk).resolve()
    if not str(target).startswith(str(MOTHER_DIR.resolve())):
        target = MOTHER_DIR / "General" / "Book_Scans"
    return target, safe_sub, safe_bk

def get_folder_tree():
    """Scan MOTHER_DIR for existing subject and book subfolders."""
    tree = {}
    if not MOTHER_DIR.exists():
        return tree

    for subj_path in sorted(MOTHER_DIR.iterdir()):
        if subj_path.is_dir() and not subj_path.name.startswith("."):
            books = []
            for bk_path in sorted(subj_path.iterdir()):
                if bk_path.is_dir() and not bk_path.name.startswith("."):
                    page_count = len(list(bk_path.glob("page_*.jpg")))
                    books.append({"name": bk_path.name, "pages": page_count})
            tree[subj_path.name] = books
    return tree

class ScannerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        try:
            msg = format % args
            clean_msg = msg.encode('ascii', errors='backslashreplace').decode('ascii')
            sys.stdout.write(f"[{self.log_date_time_string()}] {clean_msg}\n")
            sys.stdout.flush()
        except Exception:
            pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # Serve index page
        if path in ("/", "/index.html"):
            html_file = TEMPLATES_DIR / "index.html"
            if html_file.exists():
                content = html_file.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "index.html not found")
            return

        # Serve static assets
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            target = STATIC_DIR / rel_path
            if target.exists() and target.is_file():
                content = target.read_bytes()
                mime = 'application/javascript' if target.suffix == '.js' else 'text/css'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Static file not found")
            return

        # API: Status & IP
        if path == "/api/status":
            local_ip = get_local_ip()
            self.send_json({
                "local_ip": local_ip,
                "http_port": HTTP_PORT,
                "https_port": HTTPS_PORT,
                "http_url": f"http://{local_ip}:{HTTP_PORT}",
                "https_url": f"https://{local_ip}:{HTTPS_PORT}",
                "mother_dir": str(MOTHER_DIR.resolve()),
                "gdrive_connected": bool(GDRIVE_WEBHOOK_URL)
            })
            return

        # API: Folder tree
        if path == "/api/folders":
            tree = get_folder_tree()
            self.send_json({
                "mother_dir": str(MOTHER_DIR.resolve()),
                "tree": tree
            })
            return

        # API: List scanned pages in specific book
        if path == "/api/pages":
            subj = params.get("subject", ["General"])[0]
            book = params.get("book", ["Book_Scans"])[0]
            target_dir, safe_sub, safe_bk = resolve_book_dir(subj, book)
            pages = []
            if target_dir.exists():
                meta_file = target_dir / "pages.json"
                if meta_file.exists():
                    try:
                        pages = json.loads(meta_file.read_text(encoding='utf-8'))
                    except Exception:
                        pass
                else:
                    for f in sorted(target_dir.glob("page_*.jpg")):
                        pages.append({
                            "filename": f.name,
                            "page_number": int(f.stem.replace("page_", "")),
                            "score": "N/A"
                        })
            self.send_json({
                "subject": safe_sub,
                "book": safe_bk,
                "folder_path": str(target_dir.resolve()),
                "pages": pages,
                "total": len(pages)
            })
            return

        # Serve preview image
        if path.startswith("/images/"):
            parts = path[len("/images/"):].split("/")
            if len(parts) >= 3:
                subj = parts[0]
                book = parts[1]
                filename = parts[2]
                target_dir, _, _ = resolve_book_dir(subj, book)
                img_path = target_dir / filename
                if img_path.exists() and img_path.is_file():
                    content = img_path.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(content)))
                    self.send_header('Cache-Control', 'public, max-age=3600')
                    self.end_headers()
                    self.wfile.write(content)
                    return
            self.send_error(404, "Image not found")
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # API: Rapid photo upload
        if path == "/api/upload":
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_json({"success": False, "error": "Empty upload"}, 400)
                return

            img_bytes = self.rfile.read(content_length)

            subj = params.get("subject", ["General"])[0]
            book = params.get("book", ["Book_Scans"])[0]
            try:
                threshold = float(params.get("threshold", [120.0])[0])
            except ValueError:
                threshold = 120.0
            force = params.get("force", ["false"])[0].lower() in ("true", "1", "yes")

            # Client can pass its pre-computed blur score to save CPU
            client_score_str = params.get("client_score", [None])[0]
            client_score = None
            if client_score_str:
                try:
                    client_score = float(client_score_str)
                except ValueError:
                    client_score = None

            target_dir, safe_sub, safe_bk = resolve_book_dir(subj, book)

            try:
                pil_img = Image.open(io.BytesIO(img_bytes))
                pil_img = ImageOps.exif_transpose(pil_img)
            except Exception as e:
                self.send_json({"success": False, "error": f"Invalid image: {str(e)}"}, 400)
                return

            # Compute sharpness or verify client score
            if client_score is not None:
                score = client_score
            else:
                score = calculate_sharpness(pil_img)

            passed = score >= threshold or force

            if not passed:
                self.log_message(f"REJECTED (Blurry): [{safe_sub}/{safe_bk}] Score={score} < Threshold={threshold}")
                self.send_json({
                    "success": False,
                    "reason": "blurry",
                    "score": score,
                    "threshold": threshold,
                    "subject": safe_sub,
                    "book": safe_bk,
                    "message": f"Photo is blurry (Score: {score} / Min: {threshold}). Please hold steady and retake."
                })
                return

            # Target directory & atomic page numbering for multiple phones
            with save_lock:
                target_dir.mkdir(parents=True, exist_ok=True)

                meta_file = target_dir / "pages.json"
                pages = []
                if meta_file.exists():
                    try:
                        pages = json.loads(meta_file.read_text(encoding='utf-8'))
                    except Exception:
                        pages = []

                next_num = 1
                if pages:
                    next_num = max(p.get("page_number", 0) for p in pages) + 1
                else:
                    existing = list(target_dir.glob("page_*.jpg"))
                    if existing:
                        nums = [int(f.stem.replace("page_", "")) for f in existing if f.stem.replace("page_", "").isdigit()]
                        if nums:
                            next_num = max(nums) + 1

                filename = f"page_{next_num:03d}.jpg"
                save_path = target_dir / filename

                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')
                # Fast save (optimize=False for microsecond write speed)
                pil_img.save(save_path, format="JPEG", quality=90, optimize=False)

                page_info = {
                    "page_number": next_num,
                    "filename": filename,
                    "score": score,
                    "threshold": threshold,
                    "forced": force and (score < threshold),
                    "width": pil_img.width,
                    "height": pil_img.height,
                    "size_kb": round(save_path.stat().st_size / 1024, 1)
                }
                pages.append(page_info)
                meta_file.write_text(json.dumps(pages, indent=2, ensure_ascii=False), encoding='utf-8')

            self.log_message(f"SAVED: [{safe_sub}/{safe_bk}] {filename} (Score={score}, Size={page_info['size_kb']} KB)")

            # Auto-upload to Google Drive in the background (zero impact on camera capture speed)
            if GDRIVE_WEBHOOK_URL:
                upload_to_gdrive_async(safe_sub, safe_bk, filename, img_bytes, "image/jpeg")

            self.send_json({
                "success": True,
                "subject": safe_sub,
                "book": safe_bk,
                "folder_path": str(target_dir.resolve()),
                "page_number": next_num,
                "filename": filename,
                "score": score,
                "threshold": threshold,
                "total_pages": len(pages),
                "preview_url": f"/images/{urllib.parse.quote(safe_sub)}/{urllib.parse.quote(safe_bk)}/{filename}",
                "message": f"Page {next_num} saved to {safe_sub}/{safe_bk}!"
            })
            return

        # API: Delete page
        if path == "/api/delete":
            subj = params.get("subject", ["General"])[0]
            book = params.get("book", ["Book_Scans"])[0]
            filename = params.get("filename", [""])[0]
            target_dir, _, _ = resolve_book_dir(subj, book)
            target = target_dir / filename
            if target.exists() and target.is_file():
                target.unlink()
                meta_file = target_dir / "pages.json"
                if meta_file.exists():
                    try:
                        pages = json.loads(meta_file.read_text(encoding='utf-8'))
                        pages = [p for p in pages if p.get("filename") != filename]
                        meta_file.write_text(json.dumps(pages, indent=2, ensure_ascii=False), encoding='utf-8')
                    except Exception:
                        pass
                self.send_json({"success": True, "deleted": filename})
            else:
                self.send_json({"success": False, "error": "File not found"}, 404)
            return

        # API: Export PDF
        if path == "/api/export_pdf":
            subj = params.get("subject", ["General"])[0]
            book = params.get("book", ["Book_Scans"])[0]
            target_dir, safe_sub, safe_bk = resolve_book_dir(subj, book)
            if not target_dir.exists():
                self.send_json({"success": False, "error": "Folder does not exist"}, 404)
                return

            page_files = sorted(target_dir.glob("page_*.jpg"))
            if not page_files:
                self.send_json({"success": False, "error": "No pages to export"}, 400)
                return

            try:
                images = []
                for pf in page_files:
                    im = Image.open(pf)
                    if im.mode != 'RGB':
                        im = im.convert('RGB')
                    images.append(im)

                pdf_filename = f"{safe_bk}.pdf"
                pdf_path = target_dir / pdf_filename
                images[0].save(pdf_path, save_all=True, append_images=images[1:], resolution=150.0)

                if GDRIVE_WEBHOOK_URL:
                    upload_to_gdrive_async(safe_sub, safe_bk, pdf_filename, pdf_path.read_bytes(), "application/pdf")

                self.send_json({
                    "success": True,
                    "pdf_filename": pdf_filename,
                    "pages_count": len(images),
                    "file_path": str(pdf_path.resolve()),
                    "gdrive_synced": bool(GDRIVE_WEBHOOK_URL)
                })
            except Exception as e:
                self.send_json({"success": False, "error": f"PDF Export error: {str(e)}"}, 500)
            return

        # API: Open folder in Explorer
        if path == "/api/open_folder":
            subj = params.get("subject", [""])[0]
            book = params.get("book", [""])[0]
            if subj and book:
                target_dir, _, _ = resolve_book_dir(subj, book)
            elif subj:
                target_dir = MOTHER_DIR / sanitize_folder_segment(subj)
            else:
                target_dir = MOTHER_DIR

            target_dir.mkdir(parents=True, exist_ok=True)
            try:
                if sys.platform == 'win32':
                    os.startfile(str(target_dir.resolve()))
                    self.send_json({"success": True, "opened": str(target_dir.resolve())})
                else:
                    self.send_json({"success": True, "message": "Cloud environment - local folder explorer disabled"})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        self.send_error(404, "Not Found")

def run():
    is_cloud = "PORT" in os.environ or "RENDER" in os.environ or "SPACE_ID" in os.environ or "RAILWAY_STATIC_URL" in os.environ
    local_ip = get_local_ip()

    httpd = ThreadingHTTPServer(('0.0.0.0', HTTP_PORT), ScannerHandler)
    t_http = threading.Thread(target=httpd.serve_forever, daemon=True)
    t_http.start()

    httpsd = None
    has_ssl = False
    if not is_cloud:
        has_ssl = ensure_ssl_certificates()
        if has_ssl:
            try:
                httpsd = ThreadingHTTPServer(('0.0.0.0', HTTPS_PORT), ScannerHandler)
                ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
                httpsd.socket = ctx.wrap_socket(httpsd.socket, server_side=True)
                t_https = threading.Thread(target=httpsd.serve_forever, daemon=True)
                t_https.start()
            except Exception as e:
                print(f"Warning: Could not start HTTPS: {e}")

    print("=" * 68)
    print("       MULTI-PHONE BOOK SCANNER (CLOUD & DRIVE READY)")
    print("=" * 68)
    print(f" * Dedicated Storage Folder: {MOTHER_DIR.resolve()}")
    if GDRIVE_WEBHOOK_URL:
        print(" * Google Drive Sync:        ENABLED [Active Webhook]")
    else:
        print(" * Google Drive Sync:        DISABLED (Set GDRIVE_WEBHOOK_URL to enable)")
    print("=" * 68)
    if is_cloud:
        print(f" [+] RUNNING IN CLOUD MODE on port {HTTP_PORT}")
        print("     (SSL/HTTPS is managed automatically by your cloud host)")
    else:
        if has_ssl:
            print(" [+] EMBEDDED LIVE CAMERA LINK (Stays on same web page):")
            print(f"     -> https://{local_ip}:{HTTPS_PORT}")
            print("     (Accept self-signed certificate once on your phone)")
        print(" [+] STANDARD LINK (Fast file upload):")
        print(f"     -> http://{local_ip}:{HTTP_PORT}")
    print("=" * 68)
    print(" Features:")
    print("  - Connect MULTIPLE phones at once")
    print("  - Instant local sharpness detection (<0.05s)")
    print("  - Background Google Drive Auto-Sync")
    print("=" * 68)
    print(" Press Ctrl+C in this terminal to stop the server.\n")

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping servers...")
        httpd.shutdown()
        if httpsd:
            httpsd.shutdown()
        print("Server stopped.")

if __name__ == '__main__':
    run()
