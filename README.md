# 📖 BookScanner (Cloudflare Workers & Google Drive Ready)

A lightning-fast, multi-device mobile web scanner that turns any smartphone into an ultra-fast book digitizer. Point your camera, turn pages with **hands-free Auto-Snap**, and have every page automatically organized and uploaded **directly to Google Drive**.

---

## ⚡ Key Features

- **Embedded Live Camera Viewfinder**: Stays inside the web browser on the same screen — zero app-switching or native camera popups.
- **⚡ Hands-Free Auto-Snap**: Detects steady crisp text for 0.6s, sounds a chime, and automatically snaps the page when you turn it.
- **Sub-50ms Turnaround**: Client-side Laplacian variance sharpness detection ensures only clear, readable pages are saved.
- **☁️ Real-time Google Drive Sync**: Every page (`page_001.jpg`, `page_002.jpg`) and compiled PDFs stream straight into your Google Drive into `BookScans/<Subject>/<Book>/`.
- **In-Browser PDF Export**: Compiles all captured pages into a single PDF directly on your device and uploads it to Google Drive.
- **Multi-Phone Enabled**: Multiple contributors can scan simultaneously into different subjects/books with persistent page numbering.

---

## 🚀 Deploy to Cloudflare (Takes 30 Seconds, 100% Free)

1. Open [Cloudflare Dashboard](https://dash.cloudflare.com/) ➔ **Workers & Pages**.
2. Click **Create** ➔ **Import a repository**.
3. Connect **`rxxeron/bookscanner`**.
4. Leave the default Deploy command as `npx wrangler deploy`.
5. Click **Save and Deploy**!

Cloudflare automatically detects `wrangler.jsonc`, deploys `worker.js` and the `./public` assets, and issues an instant HTTPS URL (`https://bookscanner.<your-subdomain>.workers.dev`).

---

## ☁️ Google Drive Webhook Receiver (`google_apps_script.js`)

The scanner streams uploads directly into Google Drive via Google Apps Script (`google_apps_script.js`).
To customize the destination folder ID, set `GDRIVE_FOLDER_ID` in your Cloudflare Worker environment variables (or leave empty to auto-create `BookScans/`).

---

## 💻 Local Running (Optional)

If running locally with Python:
```bash
pip install -r requirements-local.txt
python server.py
```

---

## 📄 License
MIT License. Part of Prep404 ecosystem.
