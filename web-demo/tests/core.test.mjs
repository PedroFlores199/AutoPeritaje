import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { suppress, makeMask, predictPrice, describe } from "../core.mjs";

test("NMS preserves overlapping instances from different classes", () => {
  const rows = [
    { classId: 0, confidence: 0.9, box: [0, 0, 100, 100] },
    { classId: 0, confidence: 0.8, box: [1, 1, 99, 99] },
    { classId: 1, confidence: 0.7, box: [1, 1, 99, 99] },
  ];
  assert.deepEqual(
    suppress(rows).map((row) => row.classId),
    [0, 1],
  );
});

test("Browser LightGBM export matches 120 Python pipeline predictions", async () => {
  const model = JSON.parse(
    await readFile(new URL("../pricing.json", import.meta.url)),
  );
  const fixtures = JSON.parse(
    await readFile(new URL("./pricing-fixtures.json", import.meta.url)),
  );
  assert.equal(fixtures.length, 120);
  for (const row of fixtures) {
    const actual = predictPrice(row.values, model);
    for (const field of ["cost_eur", "lower", "upper"])
      assert.equal(actual[field], row.expected[field]);
    assert.ok(Math.abs(actual.labor_hours - row.expected.labor_hours) < 1e-7);
  }
});

test("Two-stage mask resize and letterbox agree with Python OpenCV references", async () => {
  const fixtures = JSON.parse(
    await readFile(new URL("./mask-fixtures.json", import.meta.url)),
  );
  for (const row of fixtures) {
    const actual = makeMask(
      { box: row.box, coefficients: new Float32Array(row.coefficients) },
      { dims: row.dims, data: new Float32Array(row.prototypes) },
      row.transform,
      row.width,
      row.height,
    );
    let intersection = 0,
      union = 0;
    for (let i = 0; i < actual.length; i++) {
      intersection += actual[i] & row.expected[i];
      union += actual[i] | row.expected[i];
    }
    assert.ok(
      union ? intersection / union >= 0.995 : actual.every((v) => v === 0),
    );
  }
});

test("Unmatched damage stays unpriced rather than inventing a part", () => {
  const config = {
    CLASSES: ["Dent"],
    DAMAGE_NAMES: { Dent: "Abolladura" },
    PART_NAMES: {},
    PART_REPAIR: {},
    REPAIR_MAP: { Dent: "Abolladura" },
  };
  const values = describe(
    [
      {
        classId: 0,
        confidence: 0.8,
        mask: new Uint8Array([1, 1, 0, 0]),
        originalBox: [0, 0, 2, 1],
      },
    ],
    config,
    2,
    2,
  );
  assert.equal(values[0].part, "Sin determinar");
  assert.equal(values[0].repair_part, "Sin determinar");
});
