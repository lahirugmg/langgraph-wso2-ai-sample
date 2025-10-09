import { NextRequest, NextResponse } from "next/server";

const EVIDENCE_URL =
  process.env.EVIDENCE_URL ?? "http://127.0.0.1:8003/agents/evidence/search";
const EHR_URL = process.env.EHR_URL ?? "http://127.0.0.1:8001";
const AGENT_TOKEN = process.env.AGENT_TOKEN;
const EHR_TOKEN = process.env.EHR_TOKEN;

async function fetchPatientSummary(patientId: string) {
  const base = EHR_URL.endsWith("/") ? EHR_URL : `${EHR_URL}/`;
  const url = new URL(
    `patients/${encodeURIComponent(patientId)}/summary`,
    base
  );
  const headers: Record<string, string> = { Accept: "application/json" };
  if (EHR_TOKEN) {
    headers.Authorization = `Bearer ${EHR_TOKEN}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minutes

  const response = await fetch(url, { headers, signal: controller.signal });
  clearTimeout(timeoutId);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to load patient summary");
  }
  return response.json();
}

function diagnosisFromProblems(problems: string[]): string {
  for (const item of problems) {
    if (item.toLowerCase().includes("diabetes")) {
      return item;
    }
  }
  return problems?.[0] ?? "Unknown condition";
}

async function buildEvidencePayload(body: any) {
  if (body?.age && body?.diagnosis && body?.egfr !== undefined) {
    return body;
  }

  const patientId = body?.patient_id;
  if (!patientId) {
    throw new Error("Provide either a full evidence payload or a patient_id");
  }

  const summary = await fetchPatientSummary(patientId);
  const problems: string[] = summary?.problems ?? [];
  const diagnosis = diagnosisFromProblems(problems);

  return {
    age: summary?.demographics?.age,
    diagnosis,
    egfr: summary?.last_egfr,
    comorbidities: problems.filter((problem: string) => problem !== diagnosis),
    geo: body?.geo ?? { lat: 35.15, lon: -90.05, radius_km: 25 },
  };
}

export async function POST(request: NextRequest) {
  const body = await request.json();

  try {
    const payload = await buildEvidencePayload(body);

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (AGENT_TOKEN) {
      headers.Authorization = `Bearer ${AGENT_TOKEN}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minutes

    const response = await fetch(EVIDENCE_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      const text = await response.text();
      return NextResponse.json(
        { detail: text || "Evidence Agent error" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error("Evidence Agent proxy failed", error);
    const message = error instanceof Error ? error.message : "Unexpected error";
    return NextResponse.json({ detail: message }, { status: 502 });
  }
}
