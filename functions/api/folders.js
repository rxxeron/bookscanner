export async function onRequestGet({ request, env }) {
  return new Response(JSON.stringify({
    tree: {},
    mother_dir: "Google Drive (BookScans/)"
  }), {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
