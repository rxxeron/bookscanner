const DEFAULT_WEBHOOK = "https://script.google.com/macros/s/AKfycby8Klzd5e0vimyKh61uC3URsGvgIkQR3hukjIId_WosyGuoqWj4cW4bB3VPVeIG6iIb/exec";

function getConfig(env) {
  return {
    webhookUrl: (env && env.GDRIVE_WEBHOOK_URL) || DEFAULT_WEBHOOK,
    folderId: (env && env.GDRIVE_FOLDER_ID) || ""
  };
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*"
    }
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const { webhookUrl, folderId } = getConfig(env);

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

    // API: Folders (read live folder tree from Google Drive via Apps Script)
    if (path === "/api/folders") {
      try {
        const scriptUrl = `${webhookUrl}?action=tree&folder_id=${encodeURIComponent(folderId)}`;
        const res = await fetch(scriptUrl, { method: "GET" });
        const data = await res.json();
        return jsonResponse({
          tree: (data && data.tree) ? data.tree : {},
          mother_dir: "Google Drive (BookScans/)"
        });
      } catch (err) {
        return jsonResponse({
          tree: {},
          mother_dir: "Google Drive (BookScans/)",
          warning: err.message
        });
      }
    }

    // API: Pages (list pages inside a Google Drive Subject/Book folder)
    if (path === "/api/pages") {
      const subject = url.searchParams.get("subject") || "General";
      const book = url.searchParams.get("book") || "Book_Scans";
      try {
        const scriptUrl = `${webhookUrl}?action=pages&subject=${encodeURIComponent(subject)}&book=${encodeURIComponent(book)}&folder_id=${encodeURIComponent(folderId)}`;
        const res = await fetch(scriptUrl, { method: "GET" });
        const data = await res.json();
        return jsonResponse({
          subject,
          book,
          pages: (data && data.pages) ? data.pages : [],
          next_page: (data && data.next_page) ? data.next_page : 1,
          total: (data && data.total) ? data.total : 0
        });
      } catch (err) {
        return jsonResponse({
          subject,
          book,
          pages: [],
          next_page: 1,
          total: 0,
          warning: err.message
        });
      }
    }

    // API: Proxy private Google Drive file preview image
    if (path === "/api/image") {
      const fileId = url.searchParams.get("id");
      if (!fileId) return new Response("Missing id", { status: 400 });
      try {
        const scriptUrl = `${webhookUrl}?action=image_b64&id=${encodeURIComponent(fileId)}`;
        const res = await fetch(scriptUrl, { method: "GET" });
        const data = await res.json();
        if (!data || !data.success || !data.base64) {
          return new Response("Image not found", { status: 404 });
        }
        const binStr = atob(data.base64);
        const bytes = new Uint8Array(binStr.length);
        for (let i = 0; i < binStr.length; i++) {
          bytes[i] = binStr.charCodeAt(i);
        }
        return new Response(bytes, {
          headers: {
            "Content-Type": data.mime_type || "image/jpeg",
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*"
          }
        });
      } catch (err) {
        return new Response("Error loading image", { status: 500 });
      }
    }

    // API: Upload (Images & PDFs directly to Google Drive via Apps Script Webhook)
    if (path === "/api/upload" && request.method === "POST") {
      try {
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
