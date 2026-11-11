export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
          "Access-Control-Allow-Headers": "*"
        }
      });
    }

    // API: Status
    if (path === "/api/status") {
      return jsonResponse({
        cloud: "cloudflare_workers",
        gdrive_connected: true,
        local_ip: "Cloudflare Edge",
        mother_dir: "Google Drive (BookScans/)"
      });
    }

    // API: Folders
    if (path === "/api/folders") {
      return jsonResponse({
        tree: {},
        mother_dir: "Google Drive (BookScans/)"
      });
    }

    // API: Pages
    if (path === "/api/pages") {
      const subject = url.searchParams.get("subject") || "General";
      const book = url.searchParams.get("book") || "Book_Scans";
      return jsonResponse({
        subject,
        book,
        pages: [],
        total: 0
      });
    }

    // API: Upload (Images & PDFs directly to Google Drive via Apps Script Webhook)
    if (path === "/api/upload" && request.method === "POST") {
      try {
        const webhookUrl = (env && env.GDRIVE_WEBHOOK_URL) || "https://script.google.com/macros/s/AKfycby8Klzd5e0vimyKh61uC3URsGvgIkQR3hukjIId_WosyGuoqWj4cW4bB3VPVeIG6iIb/exec";
        const folderId = (env && env.GDRIVE_FOLDER_ID) || "";

        const subject = url.searchParams.get("subject") || "General";
        const book = url.searchParams.get("book") || "Book_Scans";
        const clientPage = parseInt(url.searchParams.get("client_page") || "1", 10);
        const customFilename = url.searchParams.get("filename");
        const mimeType = url.searchParams.get("mime_type") || "image/jpeg";
        const filename = customFilename || `page_${String(clientPage).padStart(3, '0')}.jpg`;

        const arrayBuffer = await request.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);

        // Chunked base64 conversion safe for Cloudflare Workers
        let binary = "";
        const chunkSize = 8192;
        for (let i = 0; i < bytes.byteLength; i += chunkSize) {
          const chunk = bytes.subarray(i, Math.min(i + chunkSize, bytes.byteLength));
          binary += String.fromCharCode.apply(null, chunk);
        }
        const base64Data = btoa(binary);

        const payload = {
          subject,
          book,
          filename,
          mime_type: mimeType,
          image_base64: base64Data,
          folder_id: folderId
        };

        const scriptRes = await fetch(webhookUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        let gdriveData = {};
        try {
          gdriveData = await scriptRes.json();
        } catch (e) {
          gdriveData = { raw: await scriptRes.text() };
        }

        return jsonResponse({
          success: true,
          subject,
          book,
          page_number: clientPage,
          filename,
          gdrive: gdriveData
        });
      } catch (err) {
        return jsonResponse({
          success: false,
          error: err.message
        }, 500);
      }
    }

    // Serve static files from ./public
    if (env && env.ASSETS) {
      return env.ASSETS.fetch(request);
    }

    return new Response("Not Found", { status: 404 });
  }
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
