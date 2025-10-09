import { NextRequest, NextResponse } from "next/server";

const CARE_PLAN_URL =
  process.env.CARE_PLAN_URL ??
  "http://127.0.0.1:8004/agents/care-plan/recommendation";
const AGENT_TOKEN = process.env.AGENT_TOKEN;

export async function POST(request: NextRequest) {
  const payload = await request.json();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  if (AGENT_TOKEN) {
    headers.Authorization = `Bearer ${AGENT_TOKEN}`;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minutes

    const response = await fetch(CARE_PLAN_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      const body = await response.text();
      return NextResponse.json(
        { detail: body || "Care-Plan Agent error" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error("Care-Plan Agent request failed", error);
    return NextResponse.json(
      { detail: "Unable to reach Care-Plan Agent service" },
      { status: 502 }
    );
  }
}
