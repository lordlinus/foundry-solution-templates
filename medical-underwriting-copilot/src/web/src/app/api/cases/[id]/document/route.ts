import { getFile } from "@/lib/foundry";
import { CASE_ID } from "@/lib/ocr";
import { signedInUser, unauthorized } from "@/lib/user";

// The original PDF, from the signed-in user's own agent session.
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const user = signedInUser(request.headers);
  if (!user) return unauthorized();
  const { id } = await params;
  if (!CASE_ID.test(id)) return new Response("Invalid case.", { status: 400 });
  try {
    const pdf = await getFile(user, `cases/${id}.pdf`);
    return new Response(new Uint8Array(pdf), { headers: { "Content-Type": "application/pdf" } });
  } catch {
    return new Response("Unknown case.", { status: 404 });
  }
}
