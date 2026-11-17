export function overlap(a, b) {
  const width = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const height = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const intersection = width * height;
  return (
    intersection /
    Math.max(
      1e-9,
      (a[2] - a[0]) * (a[3] - a[1]) +
        (b[2] - b[0]) * (b[3] - b[1]) -
        intersection,
    )
  );
}

export function suppress(rows, threshold = 0.45, limit = 100) {
  const sorted = [...rows].sort((a, b) => b.confidence - a.confidence),
    keep = [];
  for (const row of sorted) {
    if (
      !keep.some(
        (old) =>
          old.classId === row.classId && overlap(old.box, row.box) > threshold,
      )
    )
      keep.push(row);
    if (keep.length === limit) break;
  }
  return keep;
}

export function candidates(
  prediction,
  classCount,
  threshold,
  filterParts = false,
) {
  const count = prediction.dims[2],
    data = prediction.data,
    rows = [];
  for (let i = 0; i < count; i++) {
    let classId = 0,
      confidence = -Infinity;
    for (let c = 0; c < classCount; c++) {
      const score = data[(4 + c) * count + i];
      if (score > confidence) {
        confidence = score;
        classId = c;
      }
    }
    if (confidence < threshold || (filterParts && classId < 8)) continue;
    const x = data[i],
      y = data[count + i],
      width = data[2 * count + i],
      height = data[3 * count + i];
    const coefficients = new Float32Array(32);
    for (let j = 0; j < 32; j++)
      coefficients[j] = data[(4 + classCount + j) * count + i];
    rows.push({
      classId,
      confidence,
      box: [x - width / 2, y - height / 2, x + width / 2, y + height / 2],
      coefficients,
    });
  }
  return suppress(rows);
}

function bilinear(data, width, height, x, y) {
  x = Math.max(0, Math.min(width - 1, x));
  y = Math.max(0, Math.min(height - 1, y));
  const x0 = Math.floor(x),
    y0 = Math.floor(y),
    x1 = Math.min(width - 1, x0 + 1),
    y1 = Math.min(height - 1, y0 + 1),
    fx = x - x0,
    fy = y - y0;
  return (
    (1 - fy) * ((1 - fx) * data[y0 * width + x0] + fx * data[y0 * width + x1]) +
    fy * ((1 - fx) * data[y1 * width + x0] + fx * data[y1 * width + x1])
  );
}

export function makeMask(row, prototypes, transform, width, height) {
  const ph = prototypes.dims[2],
    pw = prototypes.dims[3],
    plane = pw * ph,
    small = new Float32Array(plane),
    size = 640;
  for (let pixel = 0; pixel < plane; pixel++) {
    let value = 0;
    for (let c = 0; c < 32; c++)
      value += row.coefficients[c] * prototypes.data[c * plane + pixel];
    small[pixel] = 1 / (1 + Math.exp(-Math.max(-35, Math.min(35, value))));
  }
  const padded = new Float32Array(size * size);
  const [x1, y1, x2, y2] = row.box.map((v) =>
    Math.trunc(Math.max(0, Math.min(size, v))),
  );
  for (let y = y1; y < y2; y++)
    for (let x = x1; x < x2; x++)
      padded[y * size + x] = bilinear(
        small,
        pw,
        ph,
        ((x + 0.5) * pw) / size - 0.5,
        ((y + 0.5) * ph) / size - 0.5,
      );
  const mask = new Uint8Array(width * height);
  for (let y = 0; y < height; y++) {
    const iy =
      transform.top +
      Math.max(
        0,
        Math.min(
          transform.newHeight - 1,
          ((y + 0.5) * transform.newHeight) / height - 0.5,
        ),
      );
    for (let x = 0; x < width; x++) {
      const ix =
        transform.left +
        Math.max(
          0,
          Math.min(
            transform.newWidth - 1,
            ((x + 0.5) * transform.newWidth) / width - 0.5,
          ),
        );
      mask[y * width + x] = bilinear(padded, size, size, ix, iy) > 0.5 ? 1 : 0;
    }
  }
  return mask;
}

export function describe(detections, config, width, height) {
  const parts = detections.filter((d) => d.classId >= 8),
    rows = [];
  for (const damage of detections.filter((d) => d.classId < 8)) {
    const area = damage.mask.reduce((a, b) => a + b, 0);
    let best = null,
      overlap = 0;
    for (const part of parts) {
      let intersection = 0;
      for (let i = 0; i < damage.mask.length; i++)
        intersection += damage.mask[i] & part.mask[i];
      const value = intersection / Math.max(area, 1);
      if (value > overlap) {
        best = part;
        overlap = value;
      }
    }
    const known = best && overlap >= 0.15,
      partClass = known ? config.CLASSES[best.classId] : null;
    const fraction = known
      ? Math.min(
          1,
          area /
            Math.max(
              1,
              best.mask.reduce((a, b) => a + b, 0),
            ),
        )
      : area / (width * height);
    const label = config.CLASSES[damage.classId];
    rows.push({
      damage: label,
      name: config.DAMAGE_NAMES[label],
      confidence: damage.confidence,
      box: damage.originalBox,
      part: known
        ? config.PART_NAMES[partClass] || partClass
        : "Sin determinar",
      part_class: partClass,
      part_overlap: overlap,
      severity: fraction > 0.35 ? 3 : fraction > 0.08 ? 2 : 1,
      area_fraction: fraction,
      repair: config.REPAIR_MAP[label],
      repair_part: known
        ? config.PART_REPAIR[partClass] || "Sin determinar"
        : "Sin determinar",
    });
  }
  return rows;
}

export function encodeFeatures(values, model) {
  const features = [];
  for (const name of model.categorical)
    for (const category of model.categories[name])
      features.push(values[name] === category ? 1 : 0);
  model.numeric.forEach((name, index) =>
    features.push(
      Number.isFinite(values[name])
        ? values[name]
        : model.numeric_medians[index],
    ),
  );
  return features;
}

function leaf(tree, features) {
  while (typeof tree !== "number") {
    const value = features[tree.f];
    tree = Number.isNaN(value)
      ? tree.d
        ? tree.l
        : tree.r
      : value <= tree.t
        ? tree.l
        : tree.r;
  }
  return tree;
}

export function predictPrice(values, model) {
  const features = encodeFeatures(values, model),
    prediction = model.trees.map((trees) =>
      trees.reduce((total, tree) => total + leaf(tree, features), 0),
    );
  const radius = Math.max(50, Math.abs(prediction[0])) * model.quantiles[0];
  return {
    cost_eur: Math.round(Math.max(0, prediction[0]) * 100) / 100,
    lower: Math.round(Math.max(0, prediction[0] - radius) * 100) / 100,
    upper: Math.round(Math.max(0, prediction[0] + radius) * 100) / 100,
    labor_hours: prediction[1],
    model_version: model.model_version,
    synthetic: true,
  };
}

export function estimates(damages, vehicle, model, month) {
  const groups = new Map();
  for (const damage of damages) {
    const key = JSON.stringify([damage.repair, damage.repair_part]);
    groups.set(key, Math.max(groups.get(key) || 0, damage.severity));
  }
  const results = [];
  let unpriced = 0;
  for (const [key, severity] of groups) {
    const [repair, part] = JSON.parse(key);
    if (part === "Sin determinar") {
      unpriced++;
      continue;
    }
    const values = {
      ...vehicle,
      month,
      repair,
      part,
      severity,
      symptom: model.tasks[repair][0],
      dtc: model.tasks[repair][1],
      labor_rate_eur: model.regions[vehicle.region],
      parts_price_index: 1,
    };
    results.push({ repair, part, ...predictPrice(values, model) });
  }
  return { results, unpriced };
}
