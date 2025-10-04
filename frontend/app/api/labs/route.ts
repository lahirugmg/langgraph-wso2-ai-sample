import { NextRequest, NextResponse } from 'next/server';

const EHR_URL = process.env.EHR_URL ?? 'http://127.0.0.1:8001';
const EHR_TOKEN = process.env.EHR_TOKEN;

function buildLabsUrl(patientId: string, names: string, lastN: string) {
  const base = EHR_URL.endsWith('/') ? EHR_URL : `${EHR_URL}/`;
  const url = new URL(`patients/${encodeURIComponent(patientId)}/labs`, base);
  if (names) url.searchParams.set('names', names);
  if (lastN) url.searchParams.set('last_n', lastN);
  return url;
}

export async function GET(request: NextRequest) {
  const patientId = request.nextUrl.searchParams.get('patientId');
  if (!patientId) {
    return NextResponse.json({ detail: 'patientId is required' }, { status: 400 });
  }

  const names = request.nextUrl.searchParams.get('names') ?? 'eGFR,A1c';
  const lastN = request.nextUrl.searchParams.get('last_n') ?? '6';

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (EHR_TOKEN) {
    headers.Authorization = `Bearer ${EHR_TOKEN}`;
  }

  try {
    const url = buildLabsUrl(patientId, names, lastN);
    const upstream = await fetch(url, { headers });

    if (!upstream.ok) {
      const text = await upstream.text();
      return NextResponse.json(
        { detail: text || 'EHR lab lookup failed' },
        { status: upstream.status },
      );
    }

    const data = await upstream.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('EHR labs request failed', error);
    return NextResponse.json(
      { detail: 'Unable to reach EHR service' },
      { status: 502 },
    );
  }
}
