import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ LOGGING
# ======================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ======================================================
# 🧠 GOOGLE GENAI CLIENT (SAFE INIT)
# ======================================================
client = None
types = None
try:
    from google import genai
    from google.genai import types as genai_types

    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        types = genai_types
        logger.info("✅ GenAI client initialized.")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY not found. AI disabled.")
except Exception as e:
    logger.warning(f"⚠️ GenAI SDK init failed: {e}")

# ======================================================
# 🏗️ REGEX ARCHITECTURE (Core)
# ======================================================

# 1) Plan extraction: non-greedy + boundary aware
PLAN_RE = re.compile(r"Plan:\s*(.*?)(?=\n\s*\n|SVG:|Code:|$)", re.DOTALL | re.IGNORECASE)

# 2) SVG extraction: full svg block
SVG_EXTRACT_RE = re.compile(r"(?s)<svg\b[^>]*>.*?</svg>")

# 3) Advanced Arabic Detection (covers main Arabic blocks + presentation forms + Arabic Math)
ARABIC_CHECK_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\U0001EE00-\U0001EEFF]"
)

# ======================================================
# 🏛️ ALMONJEZ CONSTITUTION (The Law)
# ======================================================
ALMONJEZ_CONSTITUTION = {
    "1_Hierarchy": "Headlines MUST be 2.5x-4x body size. No floating elements; align to grid.",
    "2_Contrast": "Dark text on Light BG only. Light text on Dark BG only. Use backing rects (opacity 0.8) if unsure.",
    "3_Arabic_Logic": "Arabic Title = Top/Right & Largest. English = Secondary/Bottom.",
    "4_EmptySpace": "Forbidden dead space. Fill with: Pattern (5% opacity), Service Pills, or Huge Typo.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required. No creative re-naming."
}

# ======================================================
# 🛠️ HELPERS
# ======================================================

def sanitize_json_response(raw_text: str) -> str:
    """Remove markdown fences and fix common JSON trailing commas."""
    if not raw_text:
        return "{}"
    clean = raw_text.replace("```json", "").replace("```", "").strip()
    clean = re.sub(r",\s*([\]}])", r"\1", clean)  # trailing comma fix
    return clean

def optimize_path_data(svg_code: str) -> str:
    """
    Rounds decimals to 2 places to reduce size.
    (You can extend this later to more aggressive path optimizations.)
    """
    def round_match(m):
        try:
            return f"{float(m.group(0)):.2f}"
        except Exception:
            return m.group(0)

    return re.sub(r"\d+\.\d{3,}", round_match, svg_code)

def inject_arabic_support(svg_code: str) -> str:
    """
    Inject RTL attributes into <text> nodes that contain Arabic.
    """
    def text_replacer(match):
        tag = match.group(0)
        body = re.search(r">([^<]+)<", tag)
        if body and ARABIC_CHECK_RE.search(body.group(1)):
            # inject only if missing
            if "direction=" not in tag:
                tag = tag.replace(
                    "<text",
                    '<text direction="rtl" unicode-bidi="embed" text-anchor="end" font-family="Tajawal, sans-serif"',
                    1
                )
        return tag

    return re.sub(r"<text\b[^>]*>.*?</text>", text_replacer, svg_code, flags=re.DOTALL)

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
    safe_limit_y = max(highest - 60, int(h * 0.35))

    return {
        "type": "ORGANIC_CURVES",
        "assets": {
            "curve_XL": get_path(off_XL),
            "curve_L":  get_path(off_L),
            "curve_M":  get_path(0),
        },
        "safe_limit_y": int(safe_limit_y),
        "flip_info": {
            "safe_y_bottom_mode": int(safe_limit_y),
            "safe_y_top_mode": int(h - safe_limit_y),
        }
    }

def supply_sharp_kit(width, height, seed):
    rnd = random.Random(seed)
    w, h = int(width), int(height)

    peak = int(h * rnd.uniform(0.15, 0.30))
    p_back_y = h - peak
    p_front_y = h - peak + 40

    path_back = f"M0,{h} L0,{p_back_y} L{w/2},{p_back_y-50} L{w},{p_back_y} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_front_y} L{w/2},{p_front_y-20} L{w},{p_front_y} L{w},{h} Z"

    safe_limit_y = max(min(p_back_y, p_front_y) - 80, int(h * 0.40))

    return {
        "type": "SHARP_POLYGONS",
        "assets": {"poly_back": path_back, "poly_front": path_front},
        "safe_limit_y": int(safe_limit_y),
        "flip_info": {
            "safe_y_bottom_mode": int(safe_limit_y),
            "safe_y_top_mode": int(h - safe_limit_y),
        }
    }

# ======================================================
# 🧠 INTELLIGENCE & RECIPE DATA
# ======================================================

def analyze_needs(recipe, user_msg, cat):
    msg = (user_msg or "").lower()
    recipe_text = json.dumps(recipe, ensure_ascii=False).lower()
    cat = (cat or "").lower()

    if "card" in cat:
        return "NONE", 0.65

    clean_kw = ["clean", "text only", "minimal"]
    full_bg_kw = ["full background", "texture", "image"]

    if any(x in msg for x in clean_kw):
        return "NONE", 0.60

    if any(x in msg for x in full_bg_kw):
        return ("SHARP" if "corporate" in recipe_text else "CURVE"), 0.85

    if "curve" in msg:
        return "CURVE", 0.80
    if "sharp" in msg:
        return "SHARP", 0.80

    engine = str(recipe.get("geometry_engine", "none")).lower()
    if "sharp" in engine:
        return "SHARP", 0.85
    if "wave" in engine or "curve" in engine:
        return "CURVE", 0.85

    return "NONE", 0.70

def get_recipe_data(category_name, user_prompt):
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()

    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json",
    }

    selected_path = os.path.join(base_path, "print/flyers.json")

    for key, rel_path in flexible_map.items():
        if key in cat or key in prompt:
            candidate = os.path.join(base_path, rel_path)
            if os.path.exists(candidate):
                selected_path = candidate
                break

    try:
        with open(selected_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, list) and raw:
                return random.choice(raw)
            if isinstance(raw, dict):
                return raw
    except Exception as e:
        logger.warning(f"⚠️ Recipe load failed: {e}")

    return {}

# ======================================================
# 👮‍♂️ VALIDATORS (Plan Content)
# ======================================================

def validate_plan_content(plan):
    if not isinstance(plan, dict):
        return False, "Malformed JSON Plan."

    contract = plan.get("design_contract")
    if not isinstance(contract, dict):
        return False, "Missing 'design_contract' block."

    arabic_pos = str(contract.get("arabic_position", "")).lower()
    if "top" not in arabic_pos or "right" not in arabic_pos:
        return False, "Arabic Position Violation (Must be Top-Right)."

    contrast = str(contract.get("contrast_verified", "")).upper()
    if contrast != "YES":
        return False, "Contrast check failed or not verified."

    layout = str(contract.get("layout_variant", "")).lower()
    valid_layouts = {"hero", "minimal", "full", "split", "swiss", "diagonal"}
    if layout not in valid_layouts:
        return False, f"Invalid layout variant: {layout}"

    return True, "Valid"

# ======================================================
# ✅ ROUTES
# ======================================================

@app.route("/", methods=["GET"])
def index():
    return "Almonjez V16 Geo-Engine is Online ✅"

@app.route("/gemini", methods=["POST"])
def generate():
    if not client or not types:
        return jsonify({"error": "AI client not initialized. Check GOOGLE_API_KEY / GenAI SDK."}), 500

    try:
        data = request.get_json(silent=True) or {}
        user_msg = data.get("message", "")
        cat_name = data.get("category", "general")
        width = int(data.get("width", 800))
        height = int(data.get("height", 600))

        if not user_msg.strip():
            return jsonify({"error": "No message provided"}), 400

        recipe = get_recipe_data(cat_name, user_msg)
        geo_mode, temp_setting = analyze_needs(recipe, user_msg, cat_name)
        seed = random.randint(0, 999999)

        # 1) Hard rules (indexed)
        indexed_rules = []
        layout_rules = recipe.get("layout_rules", []) or []
        typo_rules = recipe.get("typography_rules", []) or []

        for i, r in enumerate(layout_rules, 1):
            indexed_rules.append(f"LAYOUT_{i:02d}: {r}")
        for i, r in enumerate(typo_rules, 1):
            indexed_rules.append(f"TYPE_{i:02d}: {r}")

        # 2) Geo assets
        geo_instructions = ""
        assets_block = ""
        limits_info = "N/A"

        if geo_mode == "CURVE":
            geo_kit = supply_curve_kit(width, height, seed)
            assets_block = "\n".join([f"{k}: {v}" for k, v in geo_kit["assets"].items()])
            limits_info = f"BottomSafeY: {geo_kit['flip_info']['safe_y_bottom_mode']}"
            geo_instructions = f"""
--- 📐 GEO PROTOCOL: CURVES ---
STACKING ORDER (Strict Opacity Tiers):
1) Back: curve_XL (opacity 0.12)
2) Mid : curve_L  (opacity 0.45)
3) Front: curve_M (opacity 1.00)
SAFE LIMIT INFO: {limits_info}
ASSETS:
{assets_block}
"""
        elif geo_mode == "SHARP":
            geo_kit = supply_sharp_kit(width, height, seed)
            assets_block = "\n".join([f"{k}: {v}" for k, v in geo_kit["assets"].items()])
            limits_info = f"BottomSafeY: {geo_kit['flip_info']['safe_y_bottom_mode']}"
            geo_instructions = f"""
--- 📐 GEO PROTOCOL: POLYGONS ---
STACKING ORDER:
1) poly_back : solid accent (opacity 1.0)
2) poly_front: glass effect (white 0.2 + blur)
SAFE LIMIT INFO: {limits_info}
ASSETS:
{assets_block}
"""
        else:
            geo_instructions = """--- 📐 GEO PROTOCOL: MINIMAL ---
Focus on Grid, Modular Typography (ratio 1.25), and intentional white space.
"""

        # 3) Plan template (LLM must fill)
        plan_template = {
            "engine": "ALMONJEZ_V16",
            "category": cat_name,
            "geo_mode": geo_mode,
            "seed": seed,
            "design_contract": {
                "layout_variant": "hero",
                "empty_space_tactic": "pills",
                "contrast_verified": "YES",
                "arabic_position": "top_right",
                "main_rules_applied": ["1_Hierarchy", "2_Contrast", "3_Arabic_Logic"],
                "recipe_rules_applied": indexed_rules[:8]  # give it a hint, not too long
            }
        }

        sys_instructions = f"""
ROLE: Almonjez Geo-Design Architect.
GOAL: Engineering-Grade SVG for "{cat_name}".

--- 🏛️ CONSTITUTION ---
{json.dumps(ALMONJEZ_CONSTITUTION, ensure_ascii=False, indent=2)}

--- 📜 RECIPE RULES (Indexed) ---
{json.dumps(indexed_rules, ensure_ascii=False, indent=2)}

{geo_instructions}

--- ✅ OUTPUT PROTOCOL (STRICT) ---
1) Output: "Plan: " followed by JSON only (no markdown fences).
2) Output: "SVG: " followed by <svg>...</svg>.

REQUIRED PLAN SKELETON:
Plan: {json.dumps(plan_template, ensure_ascii=False)}
"""

        # =========================================================
        # 🛡️ HYBRID LOOP + VALIDATION
        # =========================================================
        max_attempts = 2
        final_svg = None
        used_model = "unknown"
        extracted_plan = None

        models = ["gemini-2.0-pro-exp-02-05", "gemini-1.5-pro"]

        for attempt in range(max_attempts):
            model_name = models[0] if attempt == 0 else models[-1]
            try:
                current_sys = sys_instructions
                if attempt > 0:
                    current_sys += "\n\n⚠️ SYSTEM ALERT: Previous attempt failed. Follow protocol exactly. Return Plan then SVG."

                response = client.models.generate_content(
                    model=model_name,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=current_sys,
                        temperature=temp_setting if attempt == 0 else 0.5,
                        max_output_tokens=8192,
                    ),
                )

                raw_text = (response.text or "").strip()
                if not raw_text:
                    logger.warning(f"❌ Attempt {attempt+1}: Empty model response.")
                    continue

                # Extract Plan
                plan_match = PLAN_RE.search(raw_text)
                if not plan_match:
                    logger.warning(f"❌ Attempt {attempt+1}: Plan Regex mismatch.")
                    continue

                raw_json = sanitize_json_response(plan_match.group(1))
                try:
                    plan = json.loads(raw_json)
                except Exception as e:
                    logger.warning(f"❌ Attempt {attempt+1}: JSON parse error: {e}")
                    continue

                ok, reason = validate_plan_content(plan)
                if not ok:
                    logger.warning(f"❌ Attempt {attempt+1}: Plan invalid: {reason}")
                    continue

                extracted_plan = plan

                # Extract SVG
                svg_match = SVG_EXTRACT_RE.search(raw_text)
                if not svg_match:
                    logger.warning(f"❌ Attempt {attempt+1}: SVG not found.")
                    continue

                final_svg = svg_match.group(0)
                used_model = model_name
                break

            except Exception as e:
                logger.error(f"⚠️ Engine error (attempt {attempt+1}): {e}")
                time.sleep(0.8)

        if not final_svg:
            return jsonify({"error": "Failed to generate valid SVG (Plan/SVG extraction failed)."}), 500

        # =========================================================
        # 🔧 POST-PROCESSING (Protocol Enforcement)
        # =========================================================
        final_svg = optimize_path_data(final_svg)
        final_svg = inject_arabic_support(final_svg)

        # Ensure xmlns
        if 'xmlns=' not in final_svg:
            final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        # Ensure viewBox
        if 'viewbox' not in final_svg.lower():
            final_svg = final_svg.replace('<svg', f'<svg viewBox="0 0 {width} {height}"', 1)

        # Blur safety net
        if 'filter=' in final_svg and '<filter' not in final_svg:
            final_svg = final_svg.replace(
                '</svg>',
                '<defs><filter id="blur"><feGaussianBlur stdDeviation="5"/></filter></defs></svg>'
            )

        protocols_enforced = [
            "PLAN_REGEX_EXTRACTION",
            "JSON_SANITIZE_AND_VALIDATE",
            "SVG_REGEX_EXTRACTION",
            "PATH_DECIMAL_ROUNDING_2DP",
            "ARABIC_RTL_INJECTION",
            "NAMESPACE_VIEWBOX_ENFORCEMENT",
        ]

        return jsonify({
            "response": final_svg,
            "meta": {
                "seed": seed,
                "model_used": used_model,
                "geo_mode": geo_mode,
                "design_plan": extracted_plan,
                "protocols_enforced": protocols_enforced,
            }
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
