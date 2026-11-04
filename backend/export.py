# ============================================================
#  Export: a run's report as Markdown, and the whole run as a ZIP
#  (code files, prototype, tests, design, README).
# ============================================================

import io
import json
import posixpath
import re
import zipfile


def report_markdown(r):
    """Readable Markdown report of a finished run."""
    lines = ["# AI Crew Report\n", f"## Requirement\n\n{r['requirement']}\n"]
    if r.get("refinement"):
        ref = r["refinement"]
        lines.append(f"> Refined ({ref['target']}): {ref['instruction']}\n")

    lines.append("## Plan\n")
    for t in r["plan"]["tasks"]:
        lines.append(f"- **[{t['priority']}] {t['title']}**: {t['description']}")
    lines.append("")

    lines.append("## Architecture\n")
    st = r["design"]["tech_stack"]
    for k, v in st.items():
        lines.append(f"- **{k}**: {', '.join(v) if isinstance(v, list) else v}")
    endpoints = r["design"].get("api_endpoints") or []
    if endpoints:
        lines.append("\n| Method | Path | Purpose |\n|---|---|---|")
        lines += [f"| {e['method']} | `{e['path']}` | {e['purpose']} |" for e in endpoints]
    lines.append("")

    lines.append("## Generated code\n")
    for d in r["dev_outputs"]:
        lines.append(f"### {d['task']}: `{d.get('filename', '')}`\n")
        if d.get("notes"):
            lines.append(f"{d['notes']}\n")
        if d.get("revision"):
            lines.append("Revised to address: " + "; ".join(d["revision"]["addressed"]) + "\n")
        lines.append(f"```{d.get('language', '')}\n{d['code']}\n```\n")

    sc = r.get("self_correction")
    if sc:
        b, a = sc["before"], sc["after"]
        lines.append("## Self-correction\n")
        lines.append(f"High findings {b['High']} → {a['High']}, Medium {b['Medium']} → {a['Medium']}, "
                     f"failed standards {b['standards_failed']} → {a['standards_failed']}.\n")

    review = r["review"]
    lines.append("## Code review\n")
    for f in review["findings"]:
        lines.append(f"- **[{f['severity']}]** {f['issue']} ({f.get('location', '')}) → {f['suggestion']}")
    for c in review.get("standards_check", []):
        lines.append(f"- {'✅' if c['status'] == 'pass' else '❌'} {c['standard']}: {c['note']}")
    lines.append(f"\n**Overall:** {review['overall_summary']}\n")

    lines.append("## Test cases\n")
    for tc in r["tests"]["test_cases"]:
        lines.append(f"### {tc['id']}. {tc['title']}\n")
        lines += [f"{i}. {s}" for i, s in enumerate(tc.get("steps", []), 1)]
        lines.append(f"\n**Expected:** {tc['expected']}\n")

    m = r.get("metrics")
    if m:
        t = m["totals"]
        cost = f"${t['cost_usd']:.4f}" if t.get("cost_usd") is not None else "n/a"
        lines.append("## Run stats\n")
        lines.append(f"{m['total_ms'] / 1000:.1f}s total ({m.get('speedup')}× faster than sequential), "
                     f"{t['calls']} LLM calls, {t['input_tokens']} input + {t['output_tokens']} output tokens, "
                     f"estimated cost {cost}.\n")
    return "\n".join(lines)


def _safe_path(name, fallback):
    """
    Model-chosen filenames go into the ZIP, so normalise them: forward slashes,
    no absolute paths, no "..", only ordinary characters.
    """
    name = (name or "").replace("\\", "/")
    parts = [re.sub(r"[^A-Za-z0-9._-]", "_", p) for p in name.split("/")]
    parts = [p for p in parts if p not in ("", ".", "..")]
    return posixpath.join(*parts) if parts else fallback


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "task"


def build_zip(run):
    """ZIP (bytes) of a finished run: src/, preview/, tests/, design.json, README.md."""
    r = run["result"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", report_markdown(r))

        used = set()
        for i, d in enumerate(r["dev_outputs"], 1):
            path = "src/" + _safe_path(d.get("filename"), f"file-{i}.txt")
            if path in used:   # two tasks picked the same filename (e.g. server.js)
                path = f"src/{_slug(d['task'])}/" + posixpath.basename(path)
            if path in used:
                path = f"src/{i}-" + posixpath.basename(path)
            used.add(path)
            z.writestr(path, d["code"])

        if (r.get("preview") or {}).get("html"):
            z.writestr("preview/index.html", r["preview"]["html"])

        z.writestr("tests/test-cases.json", json.dumps(r["tests"], indent=2, ensure_ascii=False))
        z.writestr("design.json", json.dumps({"plan": r["plan"], "design": r["design"]}, indent=2, ensure_ascii=False))
    return buf.getvalue()
