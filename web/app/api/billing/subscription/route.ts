export async function POST() {
  return Response.json(
    { detail: "Video Pro se activa únicamente con un código de invitación." },
    { status: 404, headers: { "Cache-Control": "no-store" } },
  );
}
