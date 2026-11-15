import { getFile, getRun } from "@/lib/foundry";
import { CASE_ID } from "@/lib/ocr";
import { signedInUser, unauthorized } from "@/lib/user";

// Status of a case and, once the run completes, the released report and its review.
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const user = signedInUser(request.headers);
  if (!user) return unauthorized();
  const { id } = await params;
  if (!CASE_ID.test(id)) return Response.json({ error: "Invalid case." }, { status: 400 });

  let meta: { responseId: string; filename: string; pages: number; lowConfidence: unknown[] };
  try {
    meta = JSON.parse((await getFile(user, `cases/${id}.json`)).toString("utf8"));
  } catch {
    return Response.json({ error: "Unknown case." }, { status: 404 });
  }
  const run = await getRun(user, meta.responseId);
  const body: Record<string, unknown> = { caseId: id, ...meta, ...run };
  if (run.status === "completed") {
    body.record = (await getFile(user, `cases/${id}.md`)).toString("utf8");
    try {
      Object.assign(body, JSON.parse((await getFile(user, `cases/${id}.report.json`)).toString("utf8")));
    } catch {
      body.error = "The run finished without submitting a report.";
    }
  }
  return Response.json(body);
}
