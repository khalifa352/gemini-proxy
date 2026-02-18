import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# 🔧 LOGGING
# ======================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ======================================================
# 🤖 GEMINI CLIENT
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
except Exception:
    client = None

# ======================================================
# 🏛️ ALMONJEZ CONSTITUTION (Quality Law)
# ======================================================
ALMONJEZ_CONSTITUTION = {
    "1_Hierarchy": "Headlines MUST be 3x body size. No floating elements. Use a strict grid.",
    "2_Contrast": "Dark text on Light BG only. Light text on Dark/Medium BG only. If unsure, ADD A BACKING RECT (opacity 0.80).",
    "3_Arabic": "Arabic Title = Top/Right & Largest. French/English = Secondary (smaller & below). RTL must be explicit.",
    "4_EmptySpace": "Dead space is forbidden. Fill with: subtle pattern (opacity 0.05) OR service pills OR huge typography.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required. No added taglines unless requested."
}

# ======================================================
# ✅ ROBUST REGEX (Plan / SVG / Arabic)
# ======================================================
# Plan is FIRST LINE as HTML comment: <!--{...json...}-->
PLAN_RE = re.compile(r'^\s*<!--\s*(\{.*?\})\s*-->\s*', re.DOTALL)

# Extract first valid SVG block safely
SVG_EXTRACT_RE = re.compile(r'(?s)<svg\b[^>]*>.*?</svg>')

# Arabic detection (extended Unicode ranges)
ARABIC_CHECK_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')

# Heavy strokes (decor mistake) — allow 0.5..1.5
HEAVY_STROKE_RE = re.compile(r'stroke-width=["\'](\d+(\.\d+)?)["\']', re.IGNORECASE)

# Path d numbers (for rounding)
NUM_RE = re.compile(r'(-?\d+(?:\.\d+)?)')

# ======================================================
# 🧼 SANITIZATION (LLM noise cleanup)
# ======================================================
def strip_markdown_fences(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    # Remove common fences
    t = re.sub(r"^```(?:json|svg|xml)?\s*", "", t.strip(), flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t.strip())
    return t

def remove_js_style_comments(s: str) -> str:
    # Remove //... lines
    return re.sub(r"(?m)^\s*//.*$", "", s or "")

def remove_trailing_commas(s: str) -> str:
    # Fix trailing commas in JSON: {...,} or [...,]
    s = re.sub(r",\s*([}\]])", r"\1", s or "")
    return s

def sanitize_json_string(s: str) -> str:
    s = strip_markdown_fences(s)
    s = remove_js_style_comments(s)
    s = remove_trailing_commas(s)
    return s.strip()

# ======================================================
# 📐 GEO PROTOCOL (post-processing)
# ======================================================
def round_numbers_in_path_d(d: str, decimals: int = 2) -> str:
    if not d:
        return d

    def _r(m):
        try:
            v = float(m.group(1))
            # Keep integers clean
            if abs(v - int(v)) < 1e-9:
                return str(int(v))
            return f"{v:.{decimals}f}".rstrip("0").rstrip(".")
        except Exception:
            return m.group(1)

    return NUM_RE.sub(_r, d)

def optimize_svg_paths(svg: str) -> str:
    if not svg:
        return svg

    # Round numbers inside d=""
    def repl_d(m):
        before = m.group(1)
        d_val = m.group(2)
        after = m.group(3)
        new_d = round_numbers_in_path_d(d_val, decimals=2)
        return f'{before}{new_d}{after}'

    svg = re.sub(r'(\bd=["\'])([^"\']*)(["\'])', repl_d, svg, flags=re.IGNORECASE)

    # Close filled paths that look like backgrounds (best-effort)
    def repl_path(m):
        tag = m.group(0)
        # If fill is none, skip
        fill_none = re.search(r'fill=["\']none["\']', tag, flags=re.IGNORECASE)
        if fill_none:
            return tag

        d_m = re.search(r'd=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        if not d_m:
            return tag
        d_val = d_m.group(1).strip()
        if re.search(r'[Zz]\s*$', d_val):
            return tag

        # Append Z (safe-ish for background shapes)
        new_d = d_val + " Z"
        return re.sub(r'd=["\'][^"\']+["\']', f'd="{new_d}"', tag, flags=re.IGNORECASE)

    svg = re.sub(r'<path\b[^>]*>', repl_path, svg, flags=re.IGNORECASE)
    return svg

def ensure_svg_namespace_and_viewbox(svg: str, width: int, height: int) -> str:
    if not svg:
        return svg
    if 'xmlns=' not in svg:
        svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if 'viewBox' not in svg and 'viewbox' not in svg.lower():
        svg = svg.replace('<svg', f'<svg viewBox="0 0 {width} {height}"', 1)
    return svg

def inject_blur_filter_if_needed(svg: str) -> str:
    if not svg:
        return svg
    if 'filter=' in svg and '<filter' not in svg:
        svg = svg.replace(
            '</svg>',
            '<defs><filter id="blur"><feGaussianBlur stdDeviation="5"/></filter></defs></svg>'
        )
    return svg

def detect_arabic_in_svg(svg: str) -> bool:
    if not svg:
        return False
    return bool(ARABIC_CHECK_RE.search(svg))

def enforce_rtl_for_arabic_text(svg: str, width: int) -> str:
    """
    Best-effort:
    - If Arabic exists, ensure direction:rtl and unicode-bidi:embed on text blocks.
    - Prefer text-anchor=end and x near right edge for clearly Arabic text nodes.
    """
    if not svg or not detect_arabic_in_svg(svg):
        return svg

    # Add a CSS block once (safer than editing every node)
    rtl_css = (
        "<style>"
        ".rtl{direction:rtl;unicode-bidi:embed;text-anchor:end;}"
        "</style>"
    )
    if "<style" not in svg.lower():
        svg = svg.replace("<svg", "<svg", 1)
        # inject after <svg ...>
        svg = re.sub(r'(<svg\b[^>]*>)', r'\1' + rtl_css, svg, count=1, flags=re.IGNORECASE)

    # Add class="rtl" to <text> elements that contain Arabic characters (simple heuristic)
    def repl_text(m):
        full = m.group(0)
        open_tag = m.group(1)
        content = m.group(2)
        close = m.group(3)

        if not ARABIC_CHECK_RE.search(content):
            return full

        # If already has class rtl, keep
        if re.search(r'class=["\'][^"\']*\brtl\b', open_tag, flags=re.IGNORECASE):
            return full

        # Add class
        if "class=" in open_tag:
            open_tag = re.sub(
                r'class=["\']([^"\']*)["\']',
                lambda mm: f'class="{mm.group(1)} rtl"',
                open_tag,
                flags=re.IGNORECASE
            )
        else:
            open_tag = open_tag[:-1] + ' class="rtl">'

        # If x is missing, add x near right edge
        if not re.search(r'\bx=', open_tag, flags=re.IGNORECASE):
            open_tag = open_tag[:-1] + f' x="{int(width * 0.94)}">'

        return open_tag + content + close

    svg = re.sub(r'(<text\b[^>]*>)(.*?)(</text>)', repl_text, svg, flags=re.IGNORECASE | re.DOTALL)
    return svg

def enforce_safe_zone(svg: str, width: int, height: int) -> str:
    """
    Soft enforcement:
    - Define a safe margin (6%).
    - If we see x="0" or x very small in text, push to safe margin.
    - Same for y.
    """
    if not svg:
        return svg

    safe_x = int(width * 0.06)
    safe_y = int(height * 0.06)

    def fix_xy(tag: str) -> str:
        # x
        xm = re.search(r'\bx=["\'](-?\d+(\.\d+)?)["\']', tag, flags=re.IGNORECASE)
        if xm:
            try:
                x = float(xm.group(1))
                if x < safe_x:
                    tag = re.sub(r'\bx=["\'](-?\d+(\.\d+)?)["\']', f'x="{safe_x}"', tag, flags=re.IGNORECASE)
            except Exception:
                pass
        # y
        ym = re.search(r'\by=["\'](-?\d+(\.\d+)?)["\']', tag, flags=re.IGNORECASE)
        if ym:
            try:
                y = float(ym.group(1))
                if y < safe_y:
                    tag = re.sub(r'\by=["\'](-?\d+(\.\d+)?)["\']', f'y="{safe_y}"', tag, flags=re.IGNORECASE)
            except Exception:
                pass
        return tag

    def repl_open_text(m):
        tag = m.group(0)
        return fix_xy(tag)

    svg = re.sub(r'<text\b[^>]*>', repl_open_text, svg, flags=re.IGNORECASE)
    return svg

# ======================================================
# 👮 VALIDATORS (Plan & SVG)
# ======================================================
def extract_plan(raw_text: str):
    if not raw_text:
        return None
    m = PLAN_RE.search(raw_text)
    if not m:
        return None
    try:
        json_str = sanitize_json_string(m.group(1))
        return json.loads(json_str)
    except Exception:
        return None

def validate_plan_content(plan):
    if not isinstance(plan, dict):
        return False, "Missing JSON Plan (must be first line HTML comment)."

    contract = plan.get("design_contract")
    if not isinstance(contract, dict):
        return False, "Missing 'design_contract' object."

    # Required keys
    required = ["layout_variant", "empty_space_tactic", "contrast_verified", "arabic_position", "main_rules_applied"]
    for k in required:
        if k not in contract:
            return False, f"Missing Contract Key: {k}"

    # Strict checks
    if str(contract.get("arabic_position", "")).lower() != "top_right":
        return False, "Arabic Position MUST be exactly 'top_right'."

    if str(contract.get("contrast_verified", "")).upper() != "YES":
        return False, "Contrast MUST be 'YES'."

    layout = str(contract.get("layout_variant", "")).lower()
    valid_layouts = ["hero", "minimal", "full", "split", "swiss", "diagonal"]
    if layout not in valid_layouts:
        return False, f"Invalid layout variant: {layout}"

    rules = contract.get("main_rules_applied", [])
    if not isinstance(rules, list) or len(rules) < 3:
        return False, "Must cite at least 3 rule IDs in main_rules_applied."

    return True, "Valid"

def extract_first_svg(raw_text: str):
    if not raw_text:
        return ""
    cleaned = strip_markdown_fences(raw_text)
    m = SVG_EXTRACT_RE.search(cleaned)
    return m.group(0) if m else ""

def validate_svg_quality(svg_code: str):
    if not svg_code or "<svg" not in svg_code:
        return False, "Invalid SVG (no <svg> block found)."

    # Heavy strokes
    for m in HEAVY_STROKE_RE.finditer(svg_code):
        try:
            w = float(m.group(1))
            if w > 1.5:
                return False, "Heavy stroke-width detected (>1.5px)."
        except Exception:
            continue

    # Arabic RTL enforcement (only if Arabic is present)
    if detect_arabic_in_svg(svg_code):
        low = svg_code.lower()
        has_rtl = ("direction: rtl" in low) or ("direction:rtl" in low) or ('direction="rtl"' in low)
        if not has_rtl:
            return False, "Arabic detected but RTL not enforced (missing direction: rtl)."

    return True, "OK"

# ======================================================
# 📐 GEOMETRY KITS
# ======================================================
def supply_curve_kit(width, height, seed):
    rnd = random.Random(seed)
    w, h = int(width), int(height)

    amp = int(h * rnd.uniform(0.12, 0.22))
    base_y = h
    p0_y = base_y - int(amp * rnd.uniform(0.5, 0.9))
    p3_y = base_y - int(amp * rnd.uniform(0.3, 0.6))
    c1_x = int(w * rnd.uniform(0.25, 0.45))
    c1_y = base_y - int(amp * 1.6)
    c2_x = int(w * rnd.uniform(0.65, 0.85))
    c2_y = base_y - int(amp * 0.2)

    off_L = int(rnd.uniform(20, 35))
    off_XL = int(rnd.uniform(45, 75))

    def get_path(offset):
        return f"M0,{base_y} L0,{p0_y+offset} C{c1_x},{c1_y+offset} {c2_x},{c2_y+offset} {w},{p3_y+offset} L{w},{base_y} Z"

    highest = min(p0_y, p3_y, c1_y, c2_y)
    safe_limit_y = max(highest - 60, h * 0.35)

    return {
        "type": "CURVE",
        "assets": {"curve_XL": get_path(off_XL), "curve_L": get_path(off_L), "curve_M": get_path(0)},
        "flip_info": {
            "safe_y_bottom_mode": int(safe_limit_y),
            "safe_y_top_mode": int(h - safe_limit_y)
        },
        "hint": "Bottom anchored. For top: transform='scale(1,-1) translate(0,-H)'"
    }

def supply_sharp_kit(width, height, seed):
    rnd = random.Random(seed)
    w, h = int(width), int(height)

    peak = int(h * rnd.uniform(0.15, 0.30))
    split_x = int(w * rnd.uniform(0.3, 0.7))
    p_back_y = h - peak
    p_front_y = h - peak + 40

    path_back = f"M0,{h} L0,{p_back_y} L{split_x},{p_back_y-50} L{w},{p_back_y} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_front_y} L{split_x},{p_front_y-20} L{w},{p_front_y} L{w},{h} Z"

    safe_limit_y = max(min(p_back_y, p_front_y) - 80, h * 0.40)

    return {
        "type": "SHARP",
        "assets": {"poly_back": path_back, "poly_front": path_front},
        "flip_info": {
            "safe_y_bottom_mode": int(safe_limit_y),
            "safe_y_top_mode": int(h - safe_limit_y)
        }
    }

# ======================================================
# 🧠 INTELLIGENCE
# ======================================================
def analyze_needs(recipe, user_msg, category_name="general"):
    msg = str(user_msg or "").lower()
    cat = str(category_name or "").lower()
    recipe_text = str(recipe or "").lower()

    if "card" in cat:
        return "NONE", 0.65

    clean_kw = ["clean", "text only", "minimal", "بدون أشكال", "نص فقط"]
    full_bg_kw = ["full background", "texture", "image", "خلفية كاملة", "صورة"]

    if any(x in msg for x in clean_kw):
        return "NONE", 0.60

    if any(x in msg for x in full_bg_kw):
        return ("SHARP" if "corporate" in recipe_text else "CURVE"), 0.85

    if "curve" in msg or "wave" in msg or "موج" in msg:
        return "CURVE", 0.80
    if "sharp" in msg or "geometric" in msg or "هندسي" in msg:
        return "SHARP", 0.80

    engine = str((recipe or {}).get("geometry_engine", "none")).lower()
    if "sharp" in engine:
        return "SHARP", 0.85
    if "wave" in engine or "curve" in engine:
        return "CURVE", 0.85

    return "NONE", 0.70

# ======================================================
# 📚 RECIPES
# ======================================================
def get_recipe_data(category_name, user_prompt):
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()

    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json"
    }

    selected_path = os.path.join(base_path, "print/flyers.json")
    for key, path in flexible_map.items():
        if key in cat or key in prompt:
            full_path = os.path.join(base_path, path)
            if os.path.exists(full_path):
                selected_path = full_path
                break

    try:
        with open(selected_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, list) and raw:
                return random.choice(raw)
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass

    # Fallback safe recipe
    return {
        "id": "fallback_swiss_v1",
        "description": "Swiss clean grid with strong hierarchy",
        "layout_rules": ["Use a strict grid", "Keep safe margins", "Group contact info in footer"],
        "typography_rules": ["H1 must be massive", "Use 2 font families max", "Body >= 12px"],
        "generative_rules": {"negative_space": {"target_ratio": "0.45-0.60"}}
    }

# ======================================================
# 🧾 PLAN TEMPLATE (Concrete Contract)
# ======================================================
def build_plan_template():
    # MUST be JSON (not markdown), wrapped as HTML comment in output.
    # Keys match validator exactly.
    template = {
        "design_contract": {
            "layout_variant": "hero",
            "arabic_position": "top_right",
            "contrast_verified": "YES",
            "empty_space_tactic": "service_pills",
            "main_rules_applied": ["CONSTITUTION:1_Hierarchy", "CONSTITUTION:2_Contrast", "CONSTITUTION:3_Arabic"]
        },
        "palette": {
            "primary": "#0F172A",
            "secondary": "#FFFFFF",
            "accent": "#16A34A",
            "rule": "60-30-10"
        },
        "typography": {
            "font_families_max": 2,
            "min_body_px": 12,
            "hero_scale": "3x"
        },
        "geo_protocol": {
            "mode": "AUTO",
            "opacity_stack": [0.12, 0.45, 1.0],
            "safe_margin_ratio": 0.06,
            "path_round_decimals": 2
        }
    }
    return "<!--" + json.dumps(template, ensure_ascii=False) + "-->"

# ======================================================
# 🚀 APP ROUTE (V17.0 - Corrected, Strict, Geo Enforced)
# ======================================================
@app.route("/gemini", methods=["POST"])
def generate():
    if not client:
        return jsonify({"error": "AI Error: Gemini client not initialized"}), 500

    try:
        data = request.json or {}
        user_msg = data.get("message", "")
        cat_name = data.get("category", "general")
        width, height = int(data.get("width", 800)), int(data.get("height", 600))

        recipe = get_recipe_data(cat_name, user_msg)
        geo_mode, temp_setting = analyze_needs(recipe, user_msg, cat_name)
        seed = random.randint(0, 999999)

        # 1) Indexed rules
        indexed_rules = []
        for i, r in enumerate(recipe.get("layout_rules", []), 1):
            indexed_rules.append(f"LAYOUT_{i:02d}: {r}")
        for i, r in enumerate(recipe.get("typography_rules", []), 1):
            indexed_rules.append(f"TYPE_{i:02d}: {r}")
        for k, v in recipe.get("generative_rules", {}).items():
            indexed_rules.append(f"GEN_{str(k).upper()}: {json.dumps(v, ensure_ascii=False)}")

        # 2) Geometry kit + instructions (Geo Protocol)
        geo_kit = None
        geo_instructions = ""
        if geo_mode == "CURVE":
            geo_kit = supply_curve_kit(width, height, seed)
            assets_block = "\n".join([f'ASSET {k}: "{v}"' for k, v in geo_kit["assets"].items()])
            geo_instructions = f"""
--- 📐 GEO PROTOCOL (CURVE) ---
MANDATORY LAYERING (Opacity Stack 0.12 / 0.45 / 1.0):
1) Back:  curve_XL  opacity 0.12  (texture/depth)
2) Mid:   curve_L   opacity 0.45  (depth/accent)
3) Front: curve_M   opacity 1.00  (container/anchor)
ASSETS:
{assets_block}
SAFE TEXT LIMIT (bottom mode): {geo_kit["flip_info"]["safe_y_bottom_mode"]}
"""
        elif geo_mode == "SHARP":
            geo_kit = supply_sharp_kit(width, height, seed)
            assets_block = "\n".join([f'ASSET {k}: "{v}"' for k, v in geo_kit["assets"].items()])
            geo_instructions = f"""
--- 📐 GEO PROTOCOL (SHARP) ---
MANDATORY:
1) poly_back: 100% opacity base
2) poly_front: glass overlay (white opacity 0.20) + optional blur filter
ASSETS:
{assets_block}
SAFE TEXT LIMIT (bottom mode): {geo_kit["flip_info"]["safe_y_bottom_mode"]}
"""
        else:
            geo_instructions = """
--- 📐 GEO PROTOCOL (NONE) ---
No geometry. Must compensate with:
- Huge Typography
- Pattern opacity 0.05
- Service pills / badges
"""

        # 3) Industry filler suggestion (when content short)
        filler_suggestion = "Service Pills + subtle pattern (opacity 0.05) + huge hero"
        cat_lower = str(cat_name).lower()
        if "beauty" in cat_lower or "spa" in cat_lower:
            filler_suggestion = "Soft watermark pattern (0.05) + Care/Beauty pills + elegant hero"
        elif "food" in cat_lower or "restaurant" in cat_lower:
            filler_suggestion = "Outline food icons + Fresh/Hot badges + big title"
        elif "legal" in cat_lower or "corporate" in cat_lower:
            filler_suggestion = "Swiss hairlines (0.5px, opacity 0.2) + Trusted/Expert pills + strong hero"
        elif "industrial" in cat_lower or "construction" in cat_lower:
            filler_suggestion = "Monoline technical pattern + spec pills + bold title"

        # 4) Plan template (non-empty)
        plan_template = build_plan_template()

        # 5) System Instructions (strict output contract)
        sys_instructions = f"""
ROLE: Almonjez Elite Art Director & SVG Architect.
GOAL: Produce a PRINT-READY, high-end SVG for "{cat_name}".

--- INPUT ---
Request: "{user_msg}"
Canvas: {width}x{height}
Recipe: {json.dumps(recipe.get("description",""), ensure_ascii=False)}

--- 🏛️ CONSTITUTION (LAW) ---
{json.dumps(ALMONJEZ_CONSTITUTION, ensure_ascii=False)}

--- 📜 RECIPE HARD RULES (apply >=3) ---
{json.dumps(indexed_rules, ensure_ascii=False)}

--- 🧠 SHORT TEXT POLICY ---
If text is short or sparse: MUST use "{filler_suggestion}".
Dead space is forbidden.

{geo_instructions}

--- 🇲🇷 ARABIC ENGINE (STRICT) ---
- Arabic title must be TOP RIGHT and largest.
- Any Arabic text block MUST use RTL explicitly:
  direction: rtl; unicode-bidi: embed; text-anchor: end;
- Arabic comes before French/English (visually).

--- ⛔ BLACKLIST ---
- No thick decorative strokes (>1.5px)
- No unreadable text (<12px)
- No neon on white
- No more than 2 font families
- No text crossing dividers

--- ✅ OUTPUT CONTRACT ---
Return ONLY TWO PARTS:
1) FIRST LINE: the JSON plan as HTML comment EXACTLY (fill values; no placeholders)
2) Then: one valid SVG (<svg ...> ... </svg>)
No markdown. No explanations.

FIRST LINE TEMPLATE (you MUST output this as the first line, but filled with final values):
{plan_template}
""".strip()

        # 6) Model hierarchy + strict validation loop
        models = ["gemini-2.0-pro-exp-02-05", "gemini-1.5-pro"]
        max_attempts = 2

        final_raw = None
        used_model = "unknown"
        extracted_plan = None
        fail_reason = ""

        for attempt in range(max_attempts):
            model_name = models[0] if attempt == 0 else models[-1]
            temp = temp_setting if attempt == 0 else 0.55

            current_sys = sys_instructions
            if attempt > 0:
                current_sys += f"""

⚠️ FIX REQUIRED:
Previous output failed because: {fail_reason}
You MUST:
- start with the HTML comment JSON plan
- set contrast_verified to YES after verifying contrast
- set arabic_position exactly to top_right
- then output ONE valid SVG only
"""

            try:
                logger.info(f"🔄 Attempt {attempt+1}/{max_attempts} with {model_name}")
                resp = client.models.generate_content(
                    model=model_name,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=current_sys,
                        temperature=temp,
                        max_output_tokens=8192
                    )
                )

                raw_text = resp.text or ""
                raw_text = strip_markdown_fences(raw_text)

                plan = extract_plan(raw_text)
                ok_plan, reason_plan = validate_plan_content(plan)
                if not ok_plan:
                    fail_reason = f"Plan Error: {reason_plan}"
                    continue

                svg = extract_first_svg(raw_text)
                if not svg:
                    fail_reason = "SVG Error: No <svg> block found."
                    continue

                # Post-process SVG (Geo Protocol)
                svg = ensure_svg_namespace_and_viewbox(svg, width, height)
                svg = optimize_svg_paths(svg)
                svg = enforce_safe_zone(svg, width, height)
                svg = enforce_rtl_for_arabic_text(svg, width)
                svg = inject_blur_filter_if_needed(svg)

                ok_svg, reason_svg = validate_svg_quality(svg)
                if not ok_svg:
                    fail_reason = f"SVG Quality Error: {reason_svg}"
                    continue

                # Success
                final_raw = svg
                used_model = model_name
                extracted_plan = plan
                break

            except Exception as e:
                fail_reason = f"Engine Error: {e}"
                logger.error(f"⚠️ {fail_reason}")
                if attempt < max_attempts - 1:
                    time.sleep(1)

        if not final_raw:
            return jsonify({"error": f"Failed quality check: {fail_reason}"}), 500

        return jsonify({
            "response": final_raw,
            "meta": {
                "seed": seed,
                "model_used": used_model,
                "geo_mode": geo_mode,
                "recipe_id": recipe.get("id", "unknown"),
                "design_plan": extracted_plan
            }
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
