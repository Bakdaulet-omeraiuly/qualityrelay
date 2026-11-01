// QualityRelay's acceptance tests for the contributed tolerance check (ticket 3b5fc17f).
// Run: node --test collab/sentilab-tolerance-check/check.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import handler, { evaluate } from "./api/check.mjs";

const tab = (width, extra = {}) => ({ part_id: "T", part_type: "tab", units: "mm", dims_mm: { width }, spec: { nominal: 20.0, tol: 0.5, guard_band: 0.15 }, ...extra });
const slot = (w, extra = {}) => ({ part_id: "S", part_type: "slot", units: "mm", dims_mm: { slot_inner_width: w }, spec: { nominal: 21.0, tol: 0.5, guard_band: 0.15 }, ...extra });

test("1: tab 20.02 is pass, score 0.96", () => {
  const r = evaluate(tab(20.02));
  assert.equal(r.status, 200);
  assert.equal(r.json.verdict, "pass");
  assert.equal(r.json.score, 0.96);
});

test("2: tab 21.58 is fail, score 0", () => {
  const r = evaluate(tab(21.58));
  assert.equal(r.json.verdict, "fail");
  assert.equal(r.json.score, 0);
});

test("3: slot 20.62 is review (0.12 mm from the lower limit), score 0.24", () => {
  const r = evaluate(slot(20.62));
  assert.equal(r.json.verdict, "review");
  assert.equal(r.json.score, 0.24);
});

test("4: T-RISK 20.30 with S-RISK 20.70 passes alone but does not fit (0.40 mm)", () => {
  const r = evaluate(tab(20.30, { mate: { part_id: "S-RISK-01", dims_mm: { slot_inner_width: 20.70 } } }));
  assert.equal(r.json.verdict, "pass");
  assert.equal(r.json.clearance_mm, 0.4);
  assert.equal(r.json.fit, false);
});

test("5: missing dims_mm is 422", () => {
  const { dims_mm, ...body } = tab(20.0);
  assert.equal(evaluate(body).status, 422);
});

test("6: tab 20.35 (exactly at the 0.15 guard band) is review", () => {
  assert.equal(evaluate(tab(20.35)).json.verdict, "review");
});

test("7: tab 20.50 (on the limit) is review, score 0", () => {
  const r = evaluate(tab(20.50));
  assert.equal(r.json.verdict, "review");
  assert.equal(r.json.score, 0);
});

test("8: clearance of exactly 0.50 mm is a fit", () => {
  const r = evaluate(tab(20.30, { mate: { dims_mm: { slot_inner_width: 20.80 } } }));
  assert.equal(r.json.clearance_mm, 0.5);
  assert.equal(r.json.fit, true);
});

test("9: units other than mm is 422", () => {
  assert.equal(evaluate(tab(20.0, { units: "in" })).status, 422);
});

test("10 (contributor's decision, accepted): a slot sent with the `width` key is evaluated, not rejected", () => {
  const r = evaluate({ part_type: "slot", units: "mm", dims_mm: { width: 21.0 } });
  assert.equal(r.status, 200);
  assert.equal(r.json.verdict, "pass");
});

test("a slot as the primary part computes clearance against the tab mate", () => {
  const r = evaluate(slot(21.0, { mate: { dims_mm: { width: 20.0 } } }));
  assert.equal(r.json.clearance_mm, 1.0);
  assert.equal(r.json.fit, true);
});

test("absurd and non-numeric widths are 422", () => {
  assert.equal(evaluate(tab(0)).status, 422);
  assert.equal(evaluate(tab(150)).status, 422);
  assert.equal(evaluate(tab("20.0")).status, 422);
  assert.equal(evaluate(null).status, 422);
});

function fakeRes() {
  const res = { headers: {}, statusCode: 0, body: undefined, ended: false };
  res.setHeader = (k, v) => { res.headers[k] = v; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (b) => { res.body = b; return res; };
  res.end = () => { res.ended = true; return res; };
  return res;
}

test("handler: GET is the health line, OPTIONS is 204, PUT is 405, POST evaluates", () => {
  let res = fakeRes(); handler({ method: "GET" }, res);
  assert.equal(res.statusCode, 200); assert.equal(res.body.status, "ok");
  res = fakeRes(); handler({ method: "OPTIONS" }, res);
  assert.equal(res.statusCode, 204);
  res = fakeRes(); handler({ method: "PUT" }, res);
  assert.equal(res.statusCode, 405);
  res = fakeRes(); handler({ method: "POST", body: tab(21.58) }, res);
  assert.equal(res.statusCode, 200); assert.equal(res.body.verdict, "fail");
  assert.equal(res.headers["Access-Control-Allow-Origin"], "*");
});
