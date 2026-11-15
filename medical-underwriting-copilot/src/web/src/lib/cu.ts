import { ContentUnderstandingClient } from "@azure/ai-content-understanding";
import { DefaultAzureCredential } from "@azure/identity";
import type { CuContent } from "./ocr";

let client: ContentUnderstandingClient | undefined;

// prebuilt-layout returns markdown with page breaks and per-word OCR confidence.
export async function analyzePdf(bytes: Uint8Array): Promise<CuContent> {
  const endpoint = process.env.CONTENT_UNDERSTANDING_ENDPOINT;
  if (!endpoint) throw new Error("CONTENT_UNDERSTANDING_ENDPOINT is not set.");
  client ??= new ContentUnderstandingClient(endpoint, new DefaultAzureCredential());
  const result = await client.analyzeBinary("prebuilt-layout", bytes, "application/pdf");
  const content = (result as { contents?: CuContent[] }).contents?.[0];
  if (!content?.markdown) throw new Error("Content Understanding returned no text.");
  return content;
}
