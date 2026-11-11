export async function onRequestGet({ request, env }) {
  return new Response(JSON.stringify({
    cloud: "cloudflare_pages",
    gdrive_connected: true,
    local_ip: "Cloudflare Edge",
    mother_dir: "Google Drive (BookScans/)"
  }), {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
