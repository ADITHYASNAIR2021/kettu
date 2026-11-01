// Fallback for shares that reach the server because the service worker is not installed yet
// (first share right after install). The worker normally answers this POST itself.
export async function POST(request: Request) {
  return Response.redirect(new URL("/?shared=missing", request.url), 303);
}

export async function GET(request: Request) {
  return Response.redirect(new URL("/", request.url), 303);
}
