import { analyzePdf } from "@/lib/cu";
import { ensureSession, putFile, startRun } from "@/lib/foundry";
import { caseRecord, lowConfidenceNumbers, newCaseId } from "@/lib/ocr";
import { signedInUser, unauthorized } from "@/lib/user";

export const maxDuration = 300;
const MAX_BYTES = 20 * 1024 * 1024;

// Upload a PDF: OCR it, put the record in the user's agent session, and start the report run.
export async function POST(request: Request): Promise<Response> {
  const user = signedInUser(request.headers);
  if (!user) return unauthorized();
  const file = (await request.formData()).get("file");
  if (!(file instanceof File) || file.type !== "application/pdf" || file.size > MAX_BYTES) {
    return Response.json({ error: "Upload one PDF of up to 20 MB." }, { status: 400 });
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  const caseId = newCaseId();
  const [content] = await Promise.all([analyzePdf(bytes), ensureSession(user)]);
  const flags = lowConfidenceNumbers(content);
  const pages = (content.markdown?.match(/<!--\s*PageBreak\s*-->/g) ?? []).length + 1;

  await putFile(user, `cases/${caseId}.pdf`, bytes);
  await putFile(user, `cases/${caseId}.md`, caseRecord(content.markdown ?? "", flags));
  const responseId = await startRun(user, caseId);
  // The run ID is stored in the user's own session, so polling never trusts an ID from the browser.
  await putFile(
    user,
    `cases/${caseId}.json`,
    JSON.stringify({ caseId, filename: file.name, pages, lowConfidence: flags, responseId }),
  );
  return Response.json({ caseId });
}
