# 📖 BookScanner (Cloud & Google Drive Ready)

A lightning-fast, multi-device mobile web scanner that turns any smartphone into an ultra-fast book digitizer. Point your camera, turn pages with **hands-free Auto-Snap**, and have every page automatically organized and uploaded **directly to Google Drive**.

---

## ⚡ Key Features

- **Embedded Live Camera Viewfinder**: Stays inside the web browser on the same screen — zero app-switching or native camera popups.
- **⚡ Hands-Free Auto-Snap**: Detects steady crisp text for 0.6s, sounds a chime, and automatically snaps the page when you turn it.
- **Sub-50ms Turnaround**: Client-side Laplacian variance sharpness detection ensures only clear, readable pages are saved.
- **☁️ Real-time Google Drive Sync**: Background async worker pushes every page (`page_001.jpg`, `page_002.jpg`) and compiled PDFs straight into your Google Drive into `BookScans/<Subject>/<Book>/`.
- **1-Click PDF Export**: Compiles all captured pages into a single high-quality PDF book with one tap.
- **Multi-Phone Enabled**: Multiple contributors can scan simultaneously into different subjects/books with zero collision.

---

## ☁️ Step 1: Set Up Google Drive Sync (Takes 60 Seconds)

1. Open [Google Apps Script](https://script.google.com) in your browser.
2. Click **+ New Project**.
3. Copy and paste the entire code from [`google_apps_script.js`](./google_apps_script.js).
4. Click **Deploy** (top right) ➔ **New deployment**.
5. Click the gear icon next to "Select type" ➔ **Web app**.
6. Set:
   - **Execute as**: `Me` (your Google email)
   - **Who has access**: `Anyone`
7. Click **Deploy**, authorize permissions with your Google account, and copy the **Web app URL** (`https://script.google.com/macros/s/.../exec`).

---

## 🚀 Step 2: Deploy to the Cloud (Render / Railway / Hugging Face)

### Deploying to Render.com (100% Free)
1. Go to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** ➔ **Web Service**.
3. Connect your GitHub repository: `https://github.com/rxxeron/bookscanner`.
4. Configure:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python server.py`
5. In **Environment Variables**, add:
   - `GDRIVE_WEBHOOK_URL` = `<your Google Apps Script Web App URL from Step 1>`
6. Click **Deploy Web Service**!
7. Render gives you an official HTTPS URL (e.g., `https://bookscanner-xxxx.onrender.com`).
   *Because this URL has a valid SSL certificate, iOS and Android browsers will open the live camera viewfinder immediately with zero warnings!*

---

## 💻 Local Running (Optional)

If running on your local machine:
```bash
pip install -r requirements.txt
python server.py
```
To test Google Drive locally, set the environment variable or copy `config.example.json` to `config.json`:
```json
{
  "gdrive_webhook_url": "https://script.google.com/macros/s/.../exec"
}
```

---

## 📄 License
MIT License. Part of Prep404 ecosystem.
