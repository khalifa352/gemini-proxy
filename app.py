#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Almonjez V16 GEO + BiDi SVG Generator (Flask)
- Validates a strict JSON "design_contract" plan.
- Extracts & validates SVG, then post-processes for:
  * Decimal precision (2)
  * Opacity tiers (0.12 / 0.45 / 1.0)
  * Safe zone constraints
  * Arabic BiDi attributes (direction="rtl", unicode-bidi, text-anchor=end)
"""

from __future__ import annotations

import os
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, request

# ======================================================
# ⚙️ SYSTEM CONFIGURATION & LOGGING
# ======================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [V16-GEO] %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ======================================================
# 🤖 GenAI Client Init (Optional)
# ======================================================
client = None
types = None

try:
    # Google GenAI SDK (newer)
    from google import genai  # type: ignore
    from google.genai import types as _types  # type: ignore

    types = _types
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
        logger.info("GenAI client initialized.")
    else:
        logger.warning("GOOGLE_API_KEY not set. AI features disabled.")
except ImportError:
    logger.warning("Google GenAI SDK not found. AI features disabled.")
except Exception as e:
    logger.error("Failed to initialize GenAI Client: %s", e)

# ======================================================
# 🧠 REGEX ENGINE
# ======================================================
# Plan extraction: tries to find a JSON object after "Plan:" or anywhere in response.
PLAN_RE = re.compile(r"Plan:\s*(.*?)(?=\n\n|SVG:|Code:|$)", re.DOTALL | re.IGNORECASE)
SVG_EXTRACT_RE = re.compile(r"(?s)<svg[^>]*>.*?</svg>")

ARABIC_EXTENDED_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)

# ======================================================
# 📐 ALMONJEZ CONSTITUTION & GEO PROTOCOL
# ======================================================
ALMONJEZ_CONSTITUTION: Dict[str, str] = {
    "1_Hierarchy": "Headlines MUST be 3x body size using Modular Scale 1.25.",
    "2_Contrast": "Strict Opacity Tiers: BG=0.12, Shape=0.45, Text=1.0.",
    "3_Arabic_BiDi": "FORCE 'direction: rtl' on Arabic text. text-anchor=end for Arabic headers.",
    "4_Geo_Safety": "Keep content within Safe Zone (5mm margin). Round coordinates to 2 decimals.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required.",
}

GEO_PROTOCOL: Dict[str, Any] = {
    "opacity_tiers": {"bg": 0.12, "mid": 0.45, "focus": 1.0},
    "precision": 2,
    "safe_margin_pct": 0.05,  # 5% margin
    "bleed_mm": 3,  # Bleed margin in mm (approx 18px at 150DPI)
    "safe_zone_mm": 5,  # Safe zone margin in mm
    "modular_scale": 1.25,  # Major Third for typography hierarchy
    "typography_sizes": {
        "body": 16,
        "subheading": 20,
        "h2": 25,
        "h1": 31,
        "display": 39,
    },
}

# ======================================================
# 🛡️ SANITIZATION (JSON)
# ======================================================
def _strip_markdown_fences(s: str) -> str:
    s = re.sub(r"```json\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"```", "", s)
    return s

def _remove_line_comments(s: str) -> str:
    # Removes // ... comments (best-effort)
    return re.sub(r"//.*", "", s)

def _extract_outermost_json(s: str) -> Optional[str]:
    """
    Best-effort: find the first '{' and the last '}' and return that slice.
    This assumes plan is a JSON object (not an array).
    """
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return s[start : end + 1]

def sanitize_json_payload(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Cleans LLM output (comments, markdown, trailing commas) and parses JSON.
    Tries:
      1) content after "Plan:"
      2) full response as fallback
    """
    if not raw_text:
        return None

    match = PLAN_RE.search(raw_text)
    candidate = match.group(1) if match else raw_text

    candidate = _remove_line_comments(candidate)
    candidate = _strip_markdown_fences(candidate)

    json_str = _extract_outermost_json(candidate)
    if not json_str:
        return None

    # Trailing commas (common LLM error)
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError as e:
        logger.error("JSON Decode Error: %s", e)
        return None

# ======================================================
# 🔧 ENGINEERING UTILS (BiDi & Geometry)
# ======================================================
def is_arabic_advanced(text: str) -> bool:
    return bool(ARABIC_EXTENDED_RE.search(text or ""))

def apply_opacity_tier(element_type: str) -> float:
    tiers = GEO_PROTOCOL["opacity_tiers"]
    t = (element_type or "").lower()

    if t in {"background", "bg", "texture"}:
        return float(tiers["bg"])
    if t in {"shape", "mid", "depth"}:
        return float(tiers["mid"])
    if t in {"text", "focus", "content"}:
        return float(tiers["focus"])

    logger.warning("Unknown element type: %s. Defaulting to focus.", element_type)
    return float(tiers["focus"])

def enforce_safe_zone(
    x: float,
    y: float,
    width: float,
    height: float,
    viewbox_width: float = 1080,
    viewbox_height: float = 1080,
) -> Tuple[float, float, float, float]:
    """
    Keeps elements within safe margins. Backgrounds can extend for bleed,
    but content should stay inset.
    """
    safe_margin = float(GEO_PROTOCOL["safe_margin_pct"]) * float(min(viewbox_width, viewbox_height))
    bleed = 18.0  # approx px for 3mm bleed @ ~150DPI

    # If an element seems like a background (negative coords), allow bleed extension.
    if x < 0:
        x -= bleed
    if y < 0:
        y -= bleed
    if x + width > viewbox_width:
        width += bleed
    if y + height > viewbox_height:
        height += bleed

    # Enforce safe inset zone
    x = max(x, safe_margin)
    y = max(y, safe_margin)
    width = min(width, viewbox_width - 2 * safe_margin)
    height = min(height, viewbox_height - 2 * safe_margin)

    return x, y, width, height

def optimize_path_data(d: str) -> str:
    """
    Rounds decimals & ensures Z on seemingly closed paths.
    Avoids unsafe/incorrect conversion of L sequences into curves.
    """
    if not d:
        return d

    # Round long floats to 2 decimals
    d = re.sub(r"(\d+\.\d{3,})", lambda m: f"{float(m.group(1)):.2f}", d)

    # If path looks closed, ensure Z
    ds = d.strip()
    if ds and ds[-1].upper() != "Z" and ds.startswith("M"):
        coords = re.findall(r"[-+]?\d*\.?\d+", ds)
        if len(coords) >= 4:
            try:
                x0, y0 = float(coords[0]), float(coords[1])
                xN, yN = float(coords[-2]), float(coords[-1])
                if abs(x0 - xN) < 0.01 and abs(y0 - yN) < 0.01:
                    d = ds + "Z"
            except Exception:
                pass

    return d

def enforce_geo_protocol(svg_code: str, viewbox_width: float = 1080, viewbox_height: float = 1080) -> str:
    """
    Post-processing pipeline:
      1) Round long floats to 2 decimals
      2) Optimize path d=
      3) Apply opacity tiers (if missing)
      4) Enforce safe zone on basic x/y/width/height elements
    """
    if not svg_code:
        return svg_code

    # 1) Round long floats
    svg_code = re.sub(r"(\d+\.\d{3,})", lambda m: f"{float(m.group(1)):.2f}", svg_code)

    # 2) Optimize paths
    svg_code = re.sub(r'd="([^"]+)"', lambda m: f'd="{optimize_path_data(m.group(1))}"', svg_code)

    # 3) Apply opacity tiers where missing
    def adjust_opacity(match: re.Match) -> str:
        tag = match.group(0)
        if re.search(r'\sopacity=["\']', tag, flags=re.IGNORECASE):
            return tag

        name = match.group(1).lower()
        if name in {"text", "tspan"}:
            element_type = "text"
        elif name in {"rect", "image"} and re.search(r'\s(fill=["\']|style=)', tag, flags=re.IGNORECASE):
            element_type = "bg"
        else:
            element_type = "shape"

        opacity = apply_opacity_tier(element_type)
        # inject before closing >
        return tag[:-1] + f' opacity="{opacity:.2f}">'

    svg_code = re.sub(r"<(rect|circle|ellipse|path|text|tspan|image)\b[^>]*>", adjust_opacity, svg_code)

    # 4) Enforce safe zones on elements that have x,y,width,height
    def adjust_coords(match: re.Match) -> str:
        tag = match.group(0)
        attrs = dict(re.findall(r'(\w+)="([^"]+)"', tag))
        needed = {"x", "y", "width", "height"}
        if not needed.issubset(attrs.keys()):
            return tag

        try:
            x, y, w, h = float(attrs["x"]), float(attrs["y"]), float(attrs["width"]), float(attrs["height"])
        except Exception:
            return tag

        x, y, w, h = enforce_safe_zone(x, y, w, h, viewbox_width, viewbox_height)

        def repl(k: str, v: float) -> str:
            return re.sub(rf'{k}="[^"]+"', f'{k}="{v:.2f}"', tag)

        tag2 = tag
        tag2 = repl("x", x)
        tag2 = repl("y", y)
        tag2 = repl("width", w)
        tag2 = repl("height", h)
        return tag2

    svg_code = re.sub(r"<(rect|image)\b[^>]*>", adjust_coords, svg_code)

    return svg_code

def inject_bidi_attributes(svg_code: str) -> str:
    """
    Adds RTL + unicode-bidi attributes to Arabic <text> blocks.
    Ensures text-anchor=end (right aligned) for Arabic.
    """
    if not svg_code:
        return svg_code

    def fix_text_block(match: re.Match) -> str:
        block = match.group(0)

        # Quick content test (includes tag + inner text)
        if not is_arabic_advanced(block):
            return block

        # Ensure direction + unicode-bidi on <text ...>
        if re.search(r"<text\b", block):
            # Add only if missing
            if not re.search(r'\sdirection=["\']rtl["\']', block, flags=re.IGNORECASE):
                block = re.sub(r"<text\b", r'<text direction="rtl" unicode-bidi="embed"', block, count=1)

            # Force anchor to end (do NOT toggle)
            if re.search(r'\stext-anchor=["\']', block, flags=re.IGNORECASE):
                block = re.sub(r'\stext-anchor=["\'](start|middle|end)["\']', ' text-anchor="end"', block, flags=re.IGNORECASE)
            else:
                block = re.sub(r"<text\b", r'<text text-anchor="end"', block, count=1)

            # Font fallback
            if not re.search(r'\sfont-family=["\']', block, flags=re.IGNORECASE):
                block = re.sub(r"<text\b", r'<text font-family="Arial, sans-serif"', block, count=1)

        return block

    return re.sub(r"<text\b[^>]*>.*?</text>", fix_text_block, svg_code, flags=re.DOTALL | re.IGNORECASE)

# ======================================================
# 👮‍♂️ VALIDATORS (Plan & SVG Quality)
# ======================================================
def validate_plan_content(plan: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    if not isinstance(plan, dict):
        return False, "Invalid JSON object."

    contract = plan.get("design_contract")
    if not isinstance(contract, dict):
        return False, "Missing 'design_contract'."

    if str(contract.get("contrast_verified", "")).strip().upper() != "YES":
        return False, "Contrast verification failed (must be 'YES')."

    rules = contract.get("main_rules_applied", [])
    if not isinstance(rules, list) or len(rules) < 3:
        return False, "Constitution violation: must cite at least 3 rules."

    return True, "Valid"

def _float_in_allowed(value: float, allowed: Tuple[float, ...], tol: float = 1e-3) -> bool:
    return any(abs(value - a) <= tol for a in allowed)

def validate_svg_quality(svg_code: str) -> Tuple[bool, str]:
    if not svg_code or "<svg" not in svg_code.lower():
        return False, "No valid SVG tag found."

    # Arabic without RTL
    text_content = re.sub(r"<[^>]+>", "", svg_code)
    if is_arabic_advanced(text_content):
        if "direction" not in svg_code.lower() or "rtl" not in svg_code.lower():
            return False, "BiDi violation: Arabic text without RTL direction."

    # Amateur stroke widths
    strokes = re.findall(r'stroke-width=["\']([\d\.]+)["\']', svg_code, flags=re.IGNORECASE)
    for w in strokes:
        try:
            if float(w) > 2.0:
                return False, "Geo protocol violation: stroke-width > 2px detected."
        except Exception:
            continue

    # Opacity tiers compliance (tolerant)
    opacities = re.findall(r'opacity=["\']([\d\.]+)["\']', svg_code, flags=re.IGNORECASE)
    allowed = tuple(float(v) for v in GEO_PROTOCOL["opacity_tiers"].values())
    for o in opacities:
        try:
            if not _float_in_allowed(float(o), allowed):
                return False, "Opacity tier violation: non-standard opacity detected."
        except Exception:
            continue

    # Unclosed curves (best-effort)
    paths = re.findall(r'<path\b[^>]*\sd="([^"]+)"', svg_code, flags=re.IGNORECASE)
    for d in paths:
        up = d.upper()
        if "C" in up and "Z" not in up:
            return False, "Curve fidelity violation: unclosed curved path detected."

    return True, "Quality OK"

# ======================================================
# 🧩 RECIPE
# ======================================================
def get_recipe_data(cat: str, prompt: str) -> Dict[str, Any]:
    # Placeholder for future dynamic recipe selection
    return {
        "id": f"v16_{cat}_{int(time.time())}",
        "layout_rules": ["Use Swiss Grid", "Apply Golden Ratio"],
        "typography_rules": ["Header: H1 Bold", "Body: Sans-serif Regular"],
    }

# ======================================================
# 🌐 ROUTES
# ======================================================
@app.get("/")
def index():
    return "Almonjez V16 Design Engine is Online! 🚀"

@app.post("/gemini")
def generate():
    if not client or types is None:
        return jsonify({"error": "AI Backend Unavailable"}), 503

    data = request.get_json(silent=True) or {}
    user_msg = str(data.get("message", "")).strip()
    if not user_msg:
        return jsonify({"error": "No message provided"}), 400

    cat_name = str(data.get("category", "general"))
    width = int(data.get("width", 1080))
    height = int(data.get("height", 1080))

    recipe = get_recipe_data(cat_name, user_msg)
    indexed_rules = [f"{k}: {v}" for k, v in ALMONJEZ_CONSTITUTION.items()]

    plan_template = """
REQUIRED JSON PLAN FORMAT:
```json
{
  "design_contract": {
    "arabic_position": "top_right",
    "contrast_verified": "YES",
    "layout_variant": "hero",
    "opacity_tiers_used": ["0.12", "0.45", "1.0"],
    "main_rules_applied": ["1_Hierarchy", "3_Arabic_BiDi", "4_Geo_Safety"]
  }
}
```
"""

    sys_instructions = f"""
ROLE: Almonjez V16 Engineering Architect.

--- 🏛️ CONSTITUTION (STRICT) ---
{json.dumps(indexed_rules, ensure_ascii=False, indent=2)}

--- 📐 GEO PROTOCOL ---
1. Opacity Tiers: Background=0.12, Shapes=0.45, Text=1.0. NO exceptions.
2. Precision: All coordinates must be rounded to 2 decimals.
3. Safe Zone: Keep important content 50px inside borders.
4. Bleed: Extend backgrounds 3mm outside cut lines.
5. Typography Hierarchy: Use Modular Scale 1.25 (Body=16px, Sub=20px, H2=25px, H1=31px, Display=39px).
6. Curve Fidelity: Close paths with Z where appropriate.

--- 🕉️ ARABIC BIDI RULES ---
1. IF Arabic text detected: Add direction="rtl" and unicode-bidi="embed" to parent <text>.
2. Set text-anchor="end" for Arabic headers (right aligned).

--- 📖 RECIPE ---
{json.dumps(recipe, ensure_ascii=False, indent=2)}

--- ✅ OUTPUT PROTOCOL ---
1. Output the JSON Plan (Strict Format).
2. Output the SVG Code (Clean, Valid XML).
{plan_template}
""".strip()

    max_attempts = 2
    final_svg: Optional[str] = None
    extracted_plan: Optional[Dict[str, Any]] = None
    used_model = "unknown"
    fail_reason = ""

    models = ["gemini-2.0-pro-exp-02-05", "gemini-2.0-flash"]

    for attempt in range(max_attempts):
        model_name = models[0] if attempt == 0 else models[-1]
        try:
            current_sys = sys_instructions
            if attempt > 0 and fail_reason:
                current_sys += f"\n\n⚠️ PREVIOUS FAILURE: {fail_reason}. COMPLY STRICTLY."

            resp = client.models.generate_content(
                model=model_name,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=current_sys,
                    temperature=0.6 if attempt == 0 else 0.4,
                ),
            )

            raw = (getattr(resp, "text", None) or "").strip()
            if not raw:
                fail_reason = "Empty model response."
                continue

            plan = sanitize_json_payload(raw)
            ok_plan, p_reason = validate_plan_content(plan)
            if not ok_plan:
                fail_reason = f"Plan Error: {p_reason}"
                logger.warning("Attempt %s failed: %s", attempt + 1, fail_reason)
                continue

            svg_match = SVG_EXTRACT_RE.search(raw)
            if not svg_match:
                fail_reason = "No valid SVG block found."
                logger.warning("Attempt %s failed: %s", attempt + 1, fail_reason)
                continue

            svg_code = svg_match.group(0)
            ok_svg, s_reason = validate_svg_quality(svg_code)
            if not ok_svg:
                fail_reason = f"SVG Quality Error: {s_reason}"
                logger.warning("Attempt %s failed: %s", attempt + 1, fail_reason)
                continue

            final_svg = svg_code
            extracted_plan = plan
            used_model = model_name
            break

        except Exception as e:
            fail_reason = str(e)
            logger.error("System Error on attempt %s: %s", attempt + 1, e)
            time.sleep(1)

    if not final_svg:
        return jsonify({"error": "V16 Compliance Failure", "details": fail_reason}), 500

    # ======================================================
    # 🔨 POST-PROCESSING
    # ======================================================
    final_svg = enforce_geo_protocol(final_svg, width, height)
    final_svg = inject_bidi_attributes(final_svg)

    # Namespace fix
    if "xmlns=" not in final_svg:
        final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)

    return jsonify(
        {
            "response": final_svg,
            "meta": {
                "model": used_model,
                "plan": extracted_plan,
                "protocol": "V16-GEO-BIDI",
            },
        }
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
