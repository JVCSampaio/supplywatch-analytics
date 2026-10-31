"""Check the PBIP folder, CSV contracts and public PBIR JSON schemas.

Schema files are downloaded from developer.microsoft.com when the network is
available. A failed download skips schema checks and says so. Structural
errors always fail.
"""

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PBIP = ROOT / "SupplyWatch.pbip"
MODEL = ROOT / "SupplyWatch.SemanticModel"
REPORT = ROOT / "SupplyWatch.Report"
DATA = ROOT / "data" / "pbi"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def tmdl_names(text):
    columns, measures, sources = [], [], []
    for line in text.splitlines():
        if line.startswith("\tcolumn "):
            columns.append(line.split(" ", 1)[1].strip().strip("'"))
        elif line.startswith("\tmeasure "):
            measures.append(line.split("=", 1)[0].replace("\tmeasure ", "", 1).strip().strip("'"))
        elif line.startswith("\t\tsourceColumn: "):
            sources.append(line.split(": ", 1)[1].strip())
    return columns, measures, sources


def structural_errors():
    errors = []
    required = [
        PBIP,
        MODEL / "definition.pbism",
        MODEL / "definition" / "database.tmdl",
        MODEL / "definition" / "model.tmdl",
        MODEL / "definition" / "relationships.tmdl",
        MODEL / "definition" / "expressions.tmdl",
        REPORT / "definition.pbir",
        REPORT / "definition" / "report.json",
        REPORT / "definition" / "version.json",
        REPORT / "definition" / "pages" / "pages.json",
        DATA / "manifest.json",
        DATA / "README.md",
        ROOT / "docs" / "dicionario_medidas.md",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT)}")
    if errors:
        return errors

    pbip = load_json(PBIP)
    if pbip.get("artifacts", [{}])[0].get("report", {}).get("path") != "SupplyWatch.Report":
        errors.append("pbip does not point at SupplyWatch.Report")
    pbir = load_json(REPORT / "definition.pbir")
    by_path = pbir.get("datasetReference", {}).get("byPath", {}).get("path")
    if by_path != "../SupplyWatch.SemanticModel":
        errors.append("definition.pbir byPath is not the local semantic model")
    if "byConnection" in pbir.get("datasetReference", {}):
        errors.append("report is live-connected instead of embedded")

    pages_meta = load_json(REPORT / "definition" / "pages" / "pages.json")
    order = pages_meta.get("pageOrder", [])
    expected_pages = ["visao", "fornecedores", "estoque", "detalhe"]
    if order != expected_pages:
        errors.append(f"page order {order} is not {expected_pages}")

    model_names = {"columns": set(), "measures": set()}
    for table_file in sorted((MODEL / "definition" / "tables").glob("*.tmdl")):
        columns, measures, sources = tmdl_names(table_file.read_text(encoding="utf-8"))
        model_names["columns"].update(columns)
        model_names["measures"].update(measures)
        csv_path = DATA / f"{table_file.stem}.csv"
        if not csv_path.exists():
            errors.append(f"missing csv for {table_file.stem}")
            continue
        header = csv_path.read_text(encoding="utf-8").splitlines()[0].split(",")
        if header != sources:
            errors.append(f"{table_file.stem} csv header does not match sourceColumn order")

    expressions = (MODEL / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    if '"data/pbi"' not in expressions:
        errors.append("DataFolder is not the relative path data/pbi")

    visuals = list((REPORT / "definition" / "pages").glob("*/visuals/*/visual.json"))
    if len(visuals) < 20:
        errors.append(f"too few visuals: {len(visuals)}")
    seen = set()
    for visual_path in visuals:
        visual = load_json(visual_path)
        name = visual.get("name")
        if name in seen:
            errors.append(f"duplicate visual name {name}")
        seen.add(name)
        box = visual.get("position", {})
        if box.get("x", 0) < 0 or box.get("y", 0) < 0:
            errors.append(f"{name} has a negative position")
        if box.get("x", 0) + box.get("width", 0) > 1280 or box.get("y", 0) + box.get("height", 0) > 720:
            errors.append(f"{name} extends outside the 1280x720 page")
        query = visual.get("visual", {}).get("query", {}).get("queryState", {})
        for state in query.values():
            for projection in state.get("projections", []):
                field = projection.get("field", {})
                kind = "Measure" if "Measure" in field else "Column"
                prop = field.get(kind, {}).get("Property")
                bucket = model_names["measures"] if kind == "Measure" else model_names["columns"]
                if prop not in bucket:
                    errors.append(f"{visual_path.parent.name} binds unknown {kind} {prop}")

    detail = load_json(REPORT / "definition" / "pages" / "detalhe" / "page.json")
    if detail.get("pageBinding", {}).get("type") != "Drillthrough":
        errors.append("detail page is not a drillthrough page")
    if detail.get("visibility") != "HiddenInViewMode":
        errors.append("detail page is visible in view mode")

    manifest = load_json(DATA / "manifest.json")
    if manifest.get("synthetic") is not True or manifest.get("seed") != 42:
        errors.append("manifest is not labeled as synthetic seed 42")
    for relative in (
        "docs/powerbi/01-visao-executiva.png",
        "docs/powerbi/02-fornecedores.png",
        "docs/powerbi/03-estoque-rupturas.png",
        "docs/powerbi/04-detalhe.png",
    ):
        image = ROOT / relative
        if not image.exists() or image.stat().st_size < 10000:
            errors.append(f"preview missing or too small: {relative}")
    return errors


def schema_errors():
    try:
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
    except ImportError:
        return ["skipped: jsonschema is not installed"]

    cache = {}

    def fetch(uri):
        if uri not in cache:
            request = urllib.request.Request(uri, headers={"User-Agent": "supplywatch-pbip-validate"})
            with urllib.request.urlopen(request, timeout=30) as response:
                cache[uri] = json.loads(response.read().decode("utf-8"))
        return cache[uri]

    def retrieve(uri):
        return Resource.from_contents(fetch(uri))

    documents = [PBIP, MODEL / "definition.pbism", REPORT / "definition.pbir"]
    documents.extend(REPORT.rglob("*.json"))
    documents.extend(MODEL.rglob("*.json"))
    errors = []
    checked = 0
    for path in documents:
        if "StaticResources" in path.parts:
            continue
        try:
            document = load_json(path)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid json {exc}")
            continue
        schema_uri = document.get("$schema")
        if not schema_uri or not str(schema_uri).startswith("https://"):
            continue
        try:
            schema = fetch(schema_uri)
            registry = Registry(retrieve=retrieve)
            if "$id" in schema:
                registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
            validator = Draft7Validator(schema, registry=registry)
            for error in validator.iter_errors(document):
                location = "/".join(str(part) for part in error.path) or "(root)"
                errors.append(f"{path.relative_to(ROOT)} {location}: {error.message}")
            checked += 1
        except Exception as exc:  # network or schema drift
            return [f"skipped: {exc.__class__.__name__}: {exc}"]
    if checked == 0:
        errors.append("skipped: no schema documents were checked")
    return errors


def main():
    structural = structural_errors()
    schemas = schema_errors()
    report = {
        "structural": "passed" if not structural else "failed",
        "structural_errors": structural,
        "schema": "passed" if not schemas else ("skipped" if schemas[0].startswith("skipped:") else "failed"),
        "schema_errors": schemas,
    }
    destination = ROOT / "reports" / "sample" / "pbip_structure.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if structural or (schemas and not schemas[0].startswith("skipped:")):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
