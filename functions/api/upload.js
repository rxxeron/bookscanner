export async function onRequestPost({ request, env }) {
  try {
    const webhookUrl = (env && env.GDRIVE_WEBHOOK_URL) || "https://script.google.com/macros/s/AKfycby8Klzd5e0vimyKh61uC3URsGvgIkQR3hukjIId_WosyGuoqWj4cW4bB3VPVeIG6iIb/exec";
    const folderId = (env && env.GDRIVE_FOLDER_ID) || "";

    const url = new URL(request.url);
    const subject = url.searchParams.get("subject") || "General";
    const book = url.searchParams.get("book") || "Book_Scans";
    const clientPage = parseInt(url.searchParams.get("client_page") || "1", 10);
    const filename = `page_${String(clientPage).padStart(3, '0')}.jpg`;

    // Read image binary from request body
    const arrayBuffer = await request.arrayBuffer();
    const bytes = new Uint8Array(arrayBuffer);
    
    // Chunked base64 conversion to avoid call stack limits on large images
    let binary = "";
    const len = bytes.byteLength;
    const chunkSize = 8192;
    for (let i = 0; i < len; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + chunkSize, len)));
    }
    const base64Data = btoa(binary);

    // Forward to Google Apps Script Webhook
    const payload = {
      subject,
      book,
      filename,
      mime_type: "image/jpeg",
      image_base64: base64Data,
      folder_id: folderId
    };

    const res = await fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    let gdriveData = {};
    try {
      gdriveData = await res.json();
    } catch (e) {
      gdriveData = { raw: await res.text() };
    }

    return new Response(JSON.stringify({
      success: true,
      subject,
      book,
      page_number: clientPage,
      filename,
      gdrive: gdriveData
    }), {
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      }
    });
  } catch (err) {
    return new Response(JSON.stringify({
      success: false,
      error: err.message
    }), {
      status: 500,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      }
    });
  }
}
