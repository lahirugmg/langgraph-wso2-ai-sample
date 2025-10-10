import { NextRequest, NextResponse } from "next/server";

const RAW_CARE_PLAN_LABS_URL =
  process.env.CARE_PLAN_LABS_URL ?? "http://127.0.0.1:8004/patients";
const CARE_PLAN_LABS_URL = RAW_CARE_PLAN_LABS_URL.trim();
const AGENT_TOKEN = process.env.AGENT_TOKEN;

const EHR_URL = (process.env.EHR_URL ?? "http://127.0.0.1:8001").trim();
const EHR_TOKEN = process.env.EHR_TOKEN;

const USE_CARE_PLAN_LABS = CARE_PLAN_LABS_URL.length > 0;

function buildCarePlanLabsUrl(patientId: string, names: string, lastN: string) {
  const base = CARE_PLAN_LABS_URL.endsWith("/")
    ? CARE_PLAN_LABS_URL
    : `${CARE_PLAN_LABS_URL}/`;
  const url = new URL(`${encodeURIComponent(patientId)}/labs`, base);
  if (names) url.searchParams.set("names", names);
  if (lastN) url.searchParams.set("last_n", lastN);
  return url;
}

function buildLegacyLabsUrl(patientId: string, names: string, lastN: string) {
  const base = EHR_URL.endsWith("/") ? EHR_URL : `${EHR_URL}/`;
  const url = new URL(`patients/${encodeURIComponent(patientId)}/labs`, base);
  if (names) url.searchParams.set("names", names);
  if (lastN) url.searchParams.set("last_n", lastN);
  return url;
}

export async function GET(request: NextRequest) {
  const patientId = request.nextUrl.searchParams.get("patientId");
  if (!patientId) {
    return NextResponse.json(
      { detail: "patientId is required" },
      { status: 400 }
    );
  }

  const names = request.nextUrl.searchParams.get("names") ?? "eGFR,A1c";
  const lastN = request.nextUrl.searchParams.get("last_n") ?? "6";

  const headers: Record<string, string> = { Accept: "application/json" };
  let targetUrl: URL;

  if (USE_CARE_PLAN_LABS) {
    targetUrl = buildCarePlanLabsUrl(patientId, names, lastN);
    if (AGENT_TOKEN) {
      headers.Authorization = `Bearer ${AGENT_TOKEN}`;
    }
  } else {
    targetUrl = buildLegacyLabsUrl(patientId, names, lastN);
    if (EHR_TOKEN) {
      headers.Authorization = `Bearer ${EHR_TOKEN}`;
    }
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minutes

    const upstream = await fetch(targetUrl, {
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!upstream.ok) {
      const text = await upstream.text();
      return NextResponse.json(
        {
          detail:
            text ||
            (USE_CARE_PLAN_LABS
              ? "Care-Plan Agent lab lookup failed"
              : "EHR lab lookup failed"),
        },
        { status: upstream.status }
      );
    }

    const data = await upstream.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(
      USE_CARE_PLAN_LABS
        ? "Care-Plan labs request failed"
        : "EHR labs request failed",
      error
    );
    return NextResponse.json(
      {
        detail: USE_CARE_PLAN_LABS
          ? "Unable to reach Care-Plan Agent labs endpoint"
          : "Unable to reach EHR service",
      },
      { status: 502 }
    );
  }
}
