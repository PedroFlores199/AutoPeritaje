import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import joblib


def tree(node):
    if "leaf_value" in node:
        return float(node["leaf_value"])
    if node["decision_type"] != "<=" or node.get("missing_type") == "Zero":
        raise ValueError("El modelo utiliza una regla no compatible con el exportador")
    return {
        "f": node["split_feature"],
        "t": float(node["threshold"]),
        "d": node["default_left"],
        "l": tree(node["left_child"]),
        "r": tree(node["right_child"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("taller_source", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    reference = json.loads((root / "web-demo/pricing.json").read_text())
    if sha256(args.artifact.read_bytes()).hexdigest() != reference["bundle_sha256"]:
        raise ValueError(
            "El artefacto no coincide con el modelo de TallerMLOps verificado"
        )
    sys.path.insert(0, str(args.taller_source.resolve()))
    from taller.domain import CATEGORICAL, NUMERIC, BRANDS, TASKS, REGIONS

    bundle = joblib.load(args.artifact)
    model = bundle["model"]
    features = model.named_steps["features"]
    encoder = features.named_transformers_["cat"]
    trees = []
    for estimator in model.named_steps["regressor"].estimators_:
        dumped = estimator.booster_.dump_model()
        if dumped["average_output"]:
            raise ValueError("El exportador espera suma de árboles de regresión")
        trees.append([tree(item["tree_structure"]) for item in dumped["tree_info"]])
    value = {
        **reference,
        "categorical": CATEGORICAL,
        "categories": {
            name: [str(v) for v in values]
            for name, values in zip(CATEGORICAL, encoder.categories_)
        },
        "numeric": NUMERIC,
        "numeric_medians": features.named_transformers_["num"]
        .named_steps["impute"]
        .statistics_.tolist(),
        "trees": trees,
        "quantiles": bundle["quantiles"].tolist(),
        "tasks": TASKS,
        "regions": REGIONS,
        "brands": BRANDS,
    }
    args.output.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
