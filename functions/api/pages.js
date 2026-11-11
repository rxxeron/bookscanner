export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const subject = url.searchParams.get("subject") || "General";
  const book = url.searchParams.get("book") || "Book_Scans";

  return new Response(JSON.stringify({
    subject,
    book,
    pages: [],
    total: 0
  }), {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
