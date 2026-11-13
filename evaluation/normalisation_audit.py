"""
Normalisation audit (P0 for N6, see docs/NORMALISATION.md).

Answers two questions with data already on disk:

1. Of the estimates whose printed cell contains a standard error, a confidence interval, stars or a
   p-value, how many did the extractor fail to parse? That is the "parsable but unparsed" gap, and it
   needs no human labels.
2. Where our rows can be joined to the human key (`data/8WR QEX Combined.xlsx`) on the numeric study
   id and a normalised outcome and arm, how often does the estimate, SE, p and N agree?

Also reports the presentation variants in the TVET hand-checks, as a format sample from a second corpus.

Usage:
    python evaluation/normalisation_audit.py
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "extraction_pipeline" / "outputs"
REPORT = ROOT / "evaluation" / "results" / f"normalisation_audit_{date.today().isoformat()}.md"
TVET = ROOT.parent.parent / "pipelines" / "TVET" / "ground_truth_datasets"

# Printed-cell patterns. The interval pattern needs whitespace after the separator, so a thousands
# separator like "(1,546)" is a number and not a confidence interval.
PAREN_NUM = re.compile(r"\(\s*[-−–]?\d[\d.,]*\s*\)")
BRACKET_PAIR = re.compile(
    r"[\[(]\s*[-−–]?\d+(?:\.\d+)?\s*[,;]\s+[-−–]?\d+(?:\.\d+)?\s*[\])]"
    r"|\[\s*[-−–]?\d+(?:\.\d+)?\s*[,;]\s*[-−–]?\d+(?:\.\d+)?\s*\]"
)
STARS = re.compile(r"\*{1,3}|†{1,2}")
P_TEXT = re.compile(r"\bp\s*[<>=]\s*0?\.\d+", re.I)
PERCENT = re.compile(r"%")
TRAILING_SE = re.compile(r"\d\s*\*{0,3}\s*[-−–]?\d[\d.,]+\s*$")


def norm_col(name: str) -> str:
    return str(name).replace("\xa0", " ").strip()


def to_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).replace("\xa0", " ").replace(",", "").replace("−", "-").replace("–", "-")
    match = re.search(r"[-−–]?\d+(?:\.\d+)?", text.replace(" ", ""))
    return float(match.group()) if match else None


def norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def audit_variants(rows: pd.DataFrame) -> Dict[str, Any]:
    present = Counter()
    unparsed = Counter()
    examples: Dict[str, list] = {}
    for _, row in rows.iterrows():
        text = str(row.get("literal_cell_text") or "")
        checks = {
            "paren SE in cell": PAREN_NUM.search(text),
            "CI bracket pair": BRACKET_PAIR.search(text),
            "stars": STARS.search(text),
            "p in cell": P_TEXT.search(text),
            "percent": PERCENT.search(text),
        }
        for name, hit in checks.items():
            if not hit:
                continue
            present[name] += 1
            missing = {
                "paren SE in cell": pd.isna(row.get("standard_error")),
                "CI bracket pair": pd.isna(row.get("ci_lower")) or pd.isna(row.get("ci_upper")),
                "stars": pd.isna(row.get("significance")),
                "p in cell": pd.isna(row.get("p_value")),
                "percent": False,
            }[name]
            if missing:
                unparsed[name] += 1
                if name not in examples:
                    examples[name] = []
                if len(examples[name]) < 3:
                    examples[name].append(text[:70])
    # The p-value often sits in its own column rather than the cell.
    if "p_value_text" in rows.columns:
        with_text = rows["p_value_text"].notna()
        present["p given in p_value_text"] = int(with_text.sum())
        unparsed["p given in p_value_text"] = int((with_text & rows["p_value"].isna()).sum())
    return {"present": present, "unparsed": unparsed, "examples": examples}


def load_ours() -> pd.DataFrame:
    frames = []
    for f in OUT.glob("*/extracted_data.csv"):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        df["__file"] = f.parent.name
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_key() -> pd.DataFrame:
    path = ROOT / "data" / "8WR QEX Combined.xlsx"
    df = pd.ExcelFile(path).parse("Sheet1")
    df.columns = [norm_col(c) for c in df.columns]
    return df


def compare_with_key(ours: pd.DataFrame, key: pd.DataFrame) -> Dict[str, Any]:
    ours = ours.copy()
    ours["study_num"] = ours["study_id"].astype(str).str.extract(r"^(\d+)$")[0]
    key["study_num"] = key["StudyID"].apply(lambda x: str(int(x)) if pd.notna(x) else None)

    human = key.rename(columns={
        "Coeff reg": "estimate", "SE reg": "se", "P value exact": "p", "N total": "n_total",
        "Outcome name": "outcome", "Treatment": "arm",
    })
    human = human.dropna(subset=["study_num", "outcome"])
    human["outcome_n"] = human["outcome"].apply(norm_text)
    human["arm_n"] = human["arm"].apply(norm_text)
    ours = ours.dropna(subset=["study_num", "outcome_name"])
    ours["outcome_n"] = ours["outcome_name"].apply(norm_text)
    ours["arm_n"] = ours["treatment_arm"].apply(norm_text)

    joinable = set(ours["study_num"]) & set(human["study_num"])
    ours_j = ours[ours["study_num"].isin(joinable)]
    human_j = human[human["study_num"].isin(joinable)]

    matches = []
    for sid, group in human_j.groupby("study_num"):
        pool = ours_j[ours_j["study_num"] == sid]
        for _, hrow in group.iterrows():
            cand = pool[pool["outcome_n"] == hrow["outcome_n"]]
            if len(cand) == 0:
                continue
            if hrow["arm_n"]:
                cand_arm = cand[cand["arm_n"] == hrow["arm_n"]]
                cand = cand_arm if len(cand_arm) else cand
            matches.append((hrow, cand.iloc[0]))

    stats = Counter()
    for hrow, orow in matches:
        stats["matched"] += 1
        for human_col, our_col in (("estimate", "coefficient"), ("se", "standard_error"),
                                   ("p", "p_value"), ("n_total", "sample_size")):
            h = to_float(hrow.get(human_col))
            o = to_float(orow.get(our_col))
            if h is not None and o is not None:
                stats[f"{human_col} both"] += 1
                if abs(h - o) < 1e-6:
                    stats[f"{human_col} equal"] += 1
        stats["human rows"] += 1
    stats["joinable studies"] = len(joinable)
    stats["human rows in joinable studies"] = len(human_j)
    stats["our rows in joinable studies"] = len(ours_j)

    # Alignment-free: does our extraction for the study contain the human value at all? This does not
    # depend on outcome-name matching, so it measures value capture rather than label agreement.
    recall = Counter()
    for sid, group in human_j.groupby("study_num"):
        pool = ours_j[ours_j["study_num"] == sid]
        ests = [v for v in (to_float(x) for x in pool["coefficient"]) if v is not None]
        ses = [v for v in (to_float(x) for x in pool["standard_error"]) if v is not None]
        for _, hrow in group.iterrows():
            h = to_float(hrow.get("estimate"))
            if h is not None:
                recall["estimate rows"] += 1
                if any(abs(h - v) < 1e-6 for v in ests):
                    recall["estimate found"] += 1
            hs = to_float(hrow.get("se"))
            if hs is not None:
                recall["se rows"] += 1
                if any(abs(hs - v) < 1e-6 for v in ses):
                    recall["se found"] += 1
    stats.update(recall)
    return dict(stats)


def tvet_variants() -> Counter:
    variants = Counter()
    if not TVET.exists():
        return variants
    for f in TVET.glob("handcheck_sheet*.csv"):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        for text in df.get("literal_text", pd.Series(dtype=object)).dropna():
            text = str(text)
            if BRACKET_PAIR.search(text):
                variants["CI bracket pair"] += 1
            if PAREN_NUM.search(text):
                variants["paren SE in cell"] += 1
            if STARS.search(text):
                variants["stars"] += 1
            if P_TEXT.search(text):
                variants["p in cell"] += 1
    return variants


def main() -> None:
    ours = load_ours()
    key = load_key()
    variants = audit_variants(ours)
    comparison = compare_with_key(ours, key)
    tvet = tvet_variants()

    lines = [
        "# Normalisation audit (P0)",
        "",
        f"Rows in our per-study extraction: {len(ours)} across {ours['study_id'].nunique()} studies. "
        f"Human key rows: {len(key)} across {key['StudyID'].nunique()} studies.",
        "",
        "## Parsable but unparsed",
        "",
        "| Variant in the printed cell | Rows with it | Of those, field not parsed |",
        "| --- | --- | --- |",
    ]
    for name in ("paren SE in cell", "CI bracket pair", "stars", "p in cell", "p given in p_value_text"):
        lines.append(f"| {name} | {variants['present'][name]} | {variants['unparsed'][name]} |")
    lines += ["", "Examples of unparsed cells:"]
    for name, exs in variants["examples"].items():
        lines.append(f"- {name}: " + "; ".join(f"`{e}`" for e in exs))
    lines += ["", "## Agreement with the human key", ""]
    c = comparison
    lines.append(f"Joinable studies (numeric id): {c.get('joinable studies', 0)}. "
                 f"Human rows in them: {c.get('human rows in joinable studies', 0)}. "
                 f"Our rows in them: {c.get('our rows in joinable studies', 0)}. "
                 f"Rows matched on outcome and arm: {c.get('matched', 0)}.")
    lines += ["", "| Field | Compared | Equal |", "| --- | --- | --- |"]
    for field in ("estimate", "se", "p", "n_total"):
        lines.append(f"| {field} | {c.get(f'{field} both', 0)} | {c.get(f'{field} equal', 0)} |")
    lines += [
        "",
        "Label-free value recall (does our extraction for the study contain the human value at all):",
        f"estimate {c.get('estimate found', 0)} of {c.get('estimate rows', 0)}, "
        f"SE {c.get('se found', 0)} of {c.get('se rows', 0)}.",
    ]
    lines += [
        "",
        "## TVET hand-check formats",
        "",
        "Second corpus, for the variant taxonomy: " + ", ".join(f"{k} {v}" for k, v in tvet.most_common()) + ".",
        "",
    ]
    report = "\n".join(lines)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nwritten to {REPORT}")


if __name__ == "__main__":
    main()
