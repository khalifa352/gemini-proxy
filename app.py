import os
import json
import logging
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SYSTEM CONFIGURATION & LOGGING
# ======================================================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - [V16-GEO] %(message)s",
)
logger = logging.getLogger("V16-GEO")

app = Flask(__name__)

client = None
types = None
try:
    from google import genai
    from google.genai import types as _types

    types = _types
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        logger.info("GenAI client initialized for V16.")
    else:
        logger.warning("GOOGLE_API_KEY missing. AI features disabled.")
except ImportError:
    logger.warning("Google GenAI SDK not found. AI features disabled.")
except Exception as e:
    logger.error(f"Failed to initialize GenAI Client: {e}")

# ======================================================
# 🧠 REGEX ENGINE (Hardened)
# ======================================================

SVG_EXTRACT_RE = re.compile(r"(?is)<svg\b[^>]*>.*?</svg>")
ARABIC_EXTENDED_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)
FENCE_RE = re.compile(r"(?is)```(?:json)?\s*(.*?)\s*```")
LINE_COMMENT_RE = re.compile(r"(?m)^\s*//.*$")
TRAILING_COMMA_RE_1 = re.compile(r",\s*}")
TRAILING_COMMA_RE_2 = re.compile(r",\s*]")

TEXT_TAG_RE = re.compile(r"(?is)<text\b([^>]*)>(.*?)</text>")

VIEWBOX_RE = re.compile(
    r'(?is)\bviewBox\s*=\s*["\']\s*([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s*["\']'
)

# ======================================================
# 📐 ALMONJEZ CONSTITUTION & GEO PROTOCOL
# ======================================================
ALMONJEZ_CONSTITUTION = {
    "1_Hierarchy": "Headlines MUST be ~3x body size using Modular Scale 1.25.",
    "2_Contrast": "Strict Opacity Tiers: BG=0.12, Shape=0.45, Text=1.0.",
    "3_Arabic_BiDi": "FORCE direction=rtl on Arabic text. Anchor end for Arabic headers.",
    "4_Geo_Safety": "Keep important content inside safe zone. Round coords to 2 decimals.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required.",
}

GEO_PROTOCOL = {
    "opacity_tiers": {"bg": 0.12, "mid": 0.45, "focus": 1.0},
    "precision": 2,
    "safe_margin_pct": 0.05,  # 5% of width/height
}

# ======================================================
# 🛡️ SANITIZATION + EXTRACTION
# ======================================================

def _strip_fences(text):
    """Remove ```json fences if present."""
    m = FENCE_RE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()

def _extract_balanced_json(text):
    """
    Extract first balanced JSON object {...} using a simple state machine.
    Avoid naive first '{' / last '}' trap.
    """
    if not text:
        return None
    s = text
    start = s.find("{")
    if start == -1:
        return None

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(s)):
        ch = s[i]

        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    return None

def sanitize_json_payload(raw_text):
    """
    1) Remove markdown fences
    2) Remove // comments
    3) Extract first balanced JSON object
    4) Fix trailing commas
    5) json.loads
    """
    if not raw_text:
        return None

    candidate = _strip_fences(raw_text)
    candidate = LINE_COMMENT_RE.sub("", candidate)

    json_str = _extract_balanced_json(candidate)
    if not json_str:
        return None

    json_str = TRAILING_COMMA_RE_1.sub("}", json_str)
    json_str = TRAILING_COMMA_RE_2.sub("]", json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        logger.debug("Failed JSON string:\n%s", json_str)
        return None

def extract_best_svg(raw_text):
    """
    Extract all SVG blocks and pick the 'best' one:
    - Prefer those that include viewBox
    - Prefer longer content (more complete)
    """
    if not raw_text:
        return None
    svgs = [m.group(0) for m in SVG_EXTRACT_RE.finditer(raw_text)]
    if not svgs:
        return None

    def score(svg):
        has_viewbox = 1 if VIEWBOX_RE.search(svg) else 0
        return (has_viewbox, len(svg))

    svgs.sort(key=score, reverse=True)
    return svgs[0]

# ======================================================
# 🔧 ENGINEERING UTILS (BiDi & Geo)
# ======================================================

def is_arabic_advanced(text):
    return bool(text and ARABIC_EXTENDED_RE.search(text))

def enforce_geo_protocol(svg_code):
    """
    Geo v1:
    - Round floats to GEO_PROTOCOL['precision'] decimals.
    Hook ready for: path closure, more advanced geometry.
    """
    if not svg_code:
        return svg_code

    prec = GEO_PROTOCOL["precision"]

    def _round(m):
        return f"{float(m.group(0)):.{prec}f}"

    # Round 3+ decimal floats
    svg_code = re.sub(r"\d+\.\d{3,}", _round, svg_code)
    return svg_code

def analyze_safe_zone(svg_code):
    """
    Analyze safe zone based on viewBox and text positions.
    Currently returns warnings only (no mutation).
    """
    warnings = []
    if not svg_code:
        return warnings

    m = VIEWBOX_RE.search(svg_code)
    if not m:
        return warnings

    try:
        min_x, min_y, width, height = map(float, m.groups())
    except Exception:
        return warnings

    margin_x = width * GEO_PROTOCOL["safe_margin_pct"]
    margin_y = height * GEO_PROTOCOL["safe_margin_pct"]

    for t in TEXT_TAG_RE.finditer(svg_code):
        attrs = t.group(1) or ""
        inner = t.group(2) or ""
        plain = re.sub(r"(?is)<[^>]+>", "", inner)

        # Only care about important text (Arabic or long strings)
        if not (is_arabic_advanced(plain) or len(plain.strip()) > 12):
            continue

        x_m = re.search(r'(?is)\bx\s*=\s*["\']\s*([\d\.\-]+)\s*["\']', attrs)
        y_m = re.search(r'(?is)\by\s*=\s*["\']\s*([\d\.\-]+)\s*["\']', attrs)
        if not x_m or not y_m:
            continue

        try:
            x = float(x_m.group(1))
            y = float(y_m.group(1))
        except Exception:
            continue

        if (
            x < min_x + margin_x
            or x > min_x + width - margin_x
            or y < min_y + margin_y
            or y > min_y + height - margin_y
        ):
            warnings.append(
                f"Text '{plain[:20]}...' appears near the edge (x={x}, y={y})."
            )

    return warnings

def inject_bidi_attributes(svg_code):
    """
    BiDi v1:
    - For <text> that contains Arabic, force direction="rtl" unicode-bidi="embed"
    - Ensure Arabic headers align right: text-anchor="end"
    """
    if not svg_code:
        return svg_code

    def repl(m):
        attrs = m.group(1) or ""
        inner = m.group(2) or ""
        plain = re.sub(r"(?is)<[^>]+>", "", inner)

        if not (is_arabic_advanced(plain) or is_arabic_advanced(inner)):
            return m.group(0)

        # Force direction + bidi
        if not re.search(r'(?is)\bdirection\s*=', attrs):
            attrs += ' direction="rtl"'
        if not re.search(r'(?is)\bunicode-bidi\s*=', attrs):
            attrs += ' unicode-bidi="embed"'

        # Anchor: start -> end, or set if missing
        if re.search(r'(?is)\btext-anchor\s*=\s*["\']\s*start\s*["\']', attrs):
            attrs = re.sub(
                r'(?is)\btext-anchor\s*=\s*["\']\s*start\s*["\']',
                'text-anchor="end"',
                attrs,
            )
        elif not re.search(r'(?is)\btext-anchor\s*=', attrs):
            attrs += ' text-anchor="end"'

        # Basic font fallback if missing
        if not re.search(r'(?is)\bfont-family\s*=', attrs):
            attrs += ' font-family="Arial, sans-serif"'

        return f"<text{attrs}>{inner}</text>"

    return TEXT_TAG_RE.sub(repl, svg_code)

# ======================================================
# 👮 VALIDATORS (Plan & SVG)
# ======================================================

def validate_plan_content(plan):
    if not isinstance(plan, dict):
        return False, "Invalid JSON object."

    contract = plan.get("design_contract")
    if not isinstance(contract, dict):
        return False, "Missing 'design_contract'."

    if str(contract.get("contrast_verified", "")).upper() != "YES":
        return False, "Contrast Verification Failed (must be 'YES')."

    rules = contract.get("main_rules_applied", [])
    if not isinstance(rules, list) or len(rules) < 3:
        return False, "Must cite at least 3 constitution rules."

    return True, "Valid"

def validate_svg_quality(svg_code):
    if not svg_code or "<svg" not in svg_code.lower():
        return False, "No valid SVG tag found."

    heavy = re.findall(
        r'(?is)\bstroke-width\s*=\s*["\']\s*([\d\.]+)\s*["\']', svg_code
    )
    for val in heavy:
        try:
            if float(val) >= 3.0:
                return False, "Geo violation: stroke-width >= 3 detected."
        except Exception:
            continue

    return True, "Quality OK"

# ======================================================
# 🚀 APP LOGIC V16 (Iron Guard)
# ======================================================

def get_recipe_data(cat, prompt):
    return {
        "id": f"v16_{cat}_{int(time.time())}",
        "layout_rules": ["Use Swiss Grid", "Apply Modular Scale 1.25"],
        "typography_rules": ["H1: Bold", "Body: Sans Regular"],
    }

@app.route("/", methods=["GET"])
def root():
    return jsonify(
        {
            "status": "ok",
            "engine": "Almonjez V16 GEO+BIDI",
            "message": "Vector Design Engine online.",
        }
    )

@app.route("/gemini", methods=["POST"])
def generate():
    if not client or not types:
        return jsonify({"error": "AI Backend Unavailable"}), 500

    try:
        data = request.json or {}
        user_msg = (data.get("message") or "").strip()
        cat_name = data.get("category", "general")

        if not user_msg:
            return jsonify({"error": "Missing 'message'"}), 400

        width = int(data.get("width", 1080))
        height = int(data.get("height", 1080))

        recipe = get_recipe_data(cat_name, user_msg)
        indexed_rules = [f"{k}: {v}" for k, v in ALMONJEZ_CONSTITUTION.items()]

        plan_template = """
REQUIRED JSON PLAN FORMAT (STRICT):
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

--- CONSTITUTION (STRICT) ---
{json.dumps(indexed_rules, indent=2, ensure_ascii=False)}

--- GEO PROTOCOL ---
1) Opacity tiers: BG=0.12, Shapes=0.45, Text=1.0 (NO exceptions)
2) Precision: round coords to 2 decimals
3) Safe Zone: keep important content 50px inside borders (simulate ~5mm)

--- ARABIC BIDI RULES ---
1) If Arabic detected: add direction="rtl" unicode-bidi="embed"
2) Arabic headers: text-anchor="end"

--- OUTPUT PROTOCOL ---
1) Output the JSON plan first (exactly as requested)
2) Output the SVG code second (valid XML)
Canvas: {width}x{height}
Recipe: {json.dumps(recipe, ensure_ascii=False)}
{plan_template}
"""

        max_attempts = 2
        used_model = "unknown"
        extracted_plan = None
        final_svg = None
        fail_reason = ""
        geo_warnings = []

        models_str = os.environ.get(
            "GEMINI_MODELS", "gemini-2.0-pro-exp-02-05,gemini-2.0-flash"
        )
        models = [m.strip() for m in models_str.split(",") if m.strip()]

        for attempt in range(max_attempts):
            model_name = models[min(attempt, len(models) - 1)]
            try:
                current_sys = sys_instructions
                if attempt > 0 and fail_reason:
                    current_sys += (
                        f"\n\nPREVIOUS FAILURE: {fail_reason}\n"
                        "Fix the issue and comply strictly with V16 GEO+BIDI."
                    )

                resp = client.models.generate_content(
                    model=model_name,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=current_sys,
                        temperature=0.6 if attempt == 0 else 0.4,
                    ),
                )

                raw = (getattr(resp, "text", "") or "").strip()
                if not raw:
                    fail_reason = "Empty response from model."
                    logger.warning(f"Attempt {attempt+1} failed: {fail_reason}")
                    continue

                plan = sanitize_json_payload(raw)
                ok_plan, p_reason = validate_plan_content(plan)
                if not ok_plan:
                    fail_reason = f"Plan Error: {p_reason}"
                    logger.warning(f"Attempt {attempt+1} failed: {fail_reason}")
                    continue

                svg_code = extract_best_svg(raw)
                if not svg_code:
                    fail_reason = "No valid SVG block found."
                    logger.warning(f"Attempt {attempt+1} failed: {fail_reason}")
                    continue

                ok_svg, s_reason = validate_svg_quality(svg_code)
                if not ok_svg:
                    fail_reason = f"SVG Error: {s_reason}"
                    logger.warning(f"Attempt {attempt+1} failed: {fail_reason}")
                    continue

                extracted_plan = plan
                final_svg = svg_code
                used_model = model_name
                break

            except Exception as e:
                fail_reason = str(e)
                logger.error(f"Attempt {attempt+1} system error: {e}")
                time.sleep(1)

        if not final_svg:
            return jsonify({"error": "V16 Compliance Failure", "details": fail_reason}), 500

        # Post-processing pipeline
        final_svg = enforce_geo_protocol(final_svg)
        final_svg = inject_bidi_attributes(final_svg)
        geo_warnings = analyze_safe_zone(final_svg)

        # Ensure SVG namespace
        if not re.search(r'(?is)\bxmlns\s*=', final_svg):
            final_svg = final_svg.replace(
                "<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1
            )

        return jsonify(
            {
                "response": final_svg,
                "meta": {
                    "model": used_model,
                    "plan": extracted_plan,
                    "protocol": "V16-GEO-BIDI",
                    "geo_warnings": geo_warnings,
                },
            }
        )

    except Exception as e:
        logger.critical(f"Fatal System Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    logger.info(f"Starting Almonjez V16 on port {port}...")
    app.run(host="0.0.0.0", port=port)
