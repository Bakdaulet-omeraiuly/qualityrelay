// Fit and tolerance check for QualityRelay's slot and tab coupons. A rule, not a model. No dependencies.
// Deploy as api/check.js on Vercel: POST /api/check. GET /api/check returns the health line.
const VERSION = "1.0";
const SERVICE = "tolerance-check";
const SPECS = { tab: { nominal: 20.0, tol: 0.5, guard_band: 0.15 }, slot: { nominal: 21.0, tol: 0.5, guard_band: 0.15 } };
const EPS = 1e-9;

const widthOf = (dims) => (dims && typeof dims === "object" ? dims.width ?? dims.slot_inner_width ?? dims.tab_width : undefined);
const validWidth = (v) => typeof v === "number" && Number.isFinite(v) && v > 0 && v <= 100;

export function evaluate(body) {
  const bad = (message) => ({ status: 422, json: { error: message, service: SERVICE, version: VERSION } });
  if (!body || typeof body !== "object" || Array.isArray(body)) return bad("the body must be a JSON object");
  if (body.units !== undefined && body.units !== "mm") return bad("units must be mm");
  if (body.dims_mm === undefined || body.dims_mm === null) return bad("dims_mm is missing");
  const width = widthOf(body.dims_mm);
  if (!validWidth(width)) return bad("the width must be a number above 0 and at most 100 mm");
  const spec = body.spec ?? SPECS[body.part_type];
  if (!spec) return bad("spec is missing, and part_type isn't tab or slot");
  for (const key of ["nominal", "tol", "guard_band"]) {
    if (typeof spec[key] !== "number" || !Number.isFinite(spec[key]) || spec[key] < 0) return bad(`spec.${key} must be a non-negative number`);
  }
  if (spec.tol === 0) return bad("spec.tol must be above 0");
  const low = spec.nominal - spec.tol;
  const high = spec.nominal + spec.tol;
  const margin = Math.min(width - low, high - width);
  const reasons = [];
  let verdict;
  if (margin < -EPS) {
    verdict = "fail";
    reasons.push(`width ${width} mm is outside ${low.toFixed(2)} to ${high.toFixed(2)} mm`);
  } else if (margin <= spec.guard_band + EPS) {
    verdict = "review";
    reasons.push(`width ${width} mm is ${margin.toFixed(2)} mm from a limit, inside the ${spec.guard_band} mm guard band`);
  } else {
    verdict = "pass";
    reasons.push(`width ${width} mm is in spec, ${margin.toFixed(2)} mm from the nearest limit`);
  }
  const json = { part_id: body.part_id ?? null, verdict, score: Math.round(Math.max(0, Math.min(1, margin / spec.tol)) * 1000) / 1000, reasons, service: SERVICE, version: VERSION };
  if (body.mate !== undefined) {
    const mateWidth = widthOf(body.mate?.dims_mm);
    if (!validWidth(mateWidth)) return bad("the mate's width must be a number above 0 and at most 100 mm");
    const slot = body.part_type === "slot" ? width : mateWidth;
    const tab = body.part_type === "slot" ? mateWidth : width;
    const clearance = Math.round((slot - tab) * 1000) / 1000;
    json.clearance_mm = clearance;
    json.fit = clearance >= 0.5 - EPS;
    reasons.push(json.fit ? `clearance ${clearance} mm meets the 0.50 mm minimum` : `clearance ${clearance} mm is below the 0.50 mm minimum`);
  }
  return { status: 200, json };
}

export default function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method === "GET") return res.status(200).json({ status: "ok", service: SERVICE, version: VERSION });
  if (req.method !== "POST") return res.status(405).json({ error: "use POST" });
  const result = evaluate(req.body);
  return res.status(result.status).json(result.json);
}
