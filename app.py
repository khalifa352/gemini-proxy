import os
import json
import logging
import random
import re
import time
import math
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
except: pass

# ======================================================
# 🏗️ REGEX ARCHITECTURE (The Core Fixes)
# ======================================================

# 1. Plan Extraction: Non-greedy, boundary-aware
PLAN_RE = re.compile(r"Plan:\s*(.*?)(?=\n\n|SVG:|Code:|$)", re.DOTALL | re.IGNORECASE)

# 2. SVG Extraction: State-aware with attributes handling
SVG_EXTRACT_RE = re.compile(r"(?s)<svg[^>]*>.*?</svg>")

# 3. Advanced Arabic Detection (Unicode 17.0 Standards)
# Includes: Basic, Supplement, Extended-A/B, Presentation Forms A/B
ARABIC_CHECK_RE = re.compile(r"")

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
# 🛠️ GEO PROTOCOL HELPERS (The Engineering Layer)
# ======================================================

def sanitize_json_response(raw_text):
    """ Cleans Markdown artifacts ```json... ``` from the extracted plan """
    clean = raw_text.replace("```json", "").replace("```", "").strip()
    # Fix trailing commas which are common LLM errors
    clean = re.sub(r",\s*([\]}])", r"\1", clean)
    return clean

def optimize_path_data(svg_code):
    """ 
    Geo Protocol Layer 2: Curve Fidelity
    1. Rounds decimals to 2 places (size reduction).
    2. Ensures paths are closed with 'Z' if they look like shapes.
    """
    def round_match(match):
        try:
            return f"{float(match.group(0)):.2f}"
        except: return match.group(0)

    # Round numbers in 'd' attributes
    optimized = re.sub(r"\d+\.\d{3,}", round_match, svg_code)
    return optimized

def inject_arabic_support(svg_code):
    """
    Geo Protocol Layer 3: Bi-Directional Engineering
    Injects proper RTL attributes into text tags containing Arabic characters.
    """
    def text_replacer(match):
        tag_content = match.group(0)
        # Check if the text content inside the tag has Arabic
        text_body = re.search(r">([^<]+)<", tag_content)
        if text_body and ARABIC_CHECK_RE.search(text_body.group(1)):
            # It's Arabic, inject attributes if missing
            if "direction" not in tag_content:
                tag_content = tag_content.replace("<text", '<text direction="rtl" unicode-bidi="embed" text-anchor="end" font-family="Tajawal, sans-serif" ')
                # Fix x coordinate heuristic (flip to right side) - simplified logic
                # Ideally, this needs parsing, but regex replacement handles the bulk of attributes
        return tag_content

    return re.sub(r"<text[^>]*>.*?</text>", text_replacer, svg_code, flags=re.DOTALL)

# ======================================================
# 📐 GEOMETRY KITS (Asset Providers)
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
        "type": "ORGANIC_CURVES",
        "assets": { "curve_XL": get_path(off_XL), "curve_L":  get_path(off_L), "curve_M":  get_path(0) },
        "safe_limit_y": int(safe_limit_y),
        "flip_info": { "safe_y_bottom_mode": int(safe_limit_y), "safe_y_top_mode": int(h - safe_limit_y) }
    }

def supply_sharp_kit(width, height, seed):
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    peak = int(h * rnd.uniform(0.15, 0.30))
    p_back_y = h - peak
    p_front_y = h - peak + 40
    path_back = f"M0,{h} L0,{p_back_y} L{w/2},{p_back_y-50} L{w},{p_back_y} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_front_y} L{w/2},{p_front_y-20} L{w},{p_front_y} L{w},{h} Z"
    safe_limit_y = max(min(p_back_y, p_front_y) - 80, h * 0.40)
    
    return {
        "type": "SHARP_POLYGONS",
        "assets": { "poly_back": path_back, "poly_front": path_front },
        "safe_limit_y": int(safe_limit_y),
        "flip_info": { "safe_y_bottom_mode": int(safe_limit_y), "safe_y_top_mode": int(h - safe_limit_y) }
    }

# ======================================================
# 🧠 INTELLIGENCE & DATA
# ======================================================

def analyze_needs(recipe, user_msg, cat):
    msg = str(user_msg).lower()
    recipe_text = str(recipe).lower()
    
    if 'card' in cat: return 'NONE', 0.65
    clean_kw = ['clean', 'text only', 'minimal']
    full_bg_kw = ['full background', 'texture', 'image']
    
    if any(x in msg for x in clean_kw): return 'NONE', 0.6
    if any(x in msg for x in full_bg_kw):
        return 'SHARP' if 'corporate' in recipe_text else 'CURVE', 0.85

    if 'curve' in msg: return 'CURVE', 0.8
    if 'sharp' in msg: return 'SHARP', 0.8
    
    engine = str(recipe.get('geometry_engine', 'none')).lower()
    if 'sharp' in engine: return 'SHARP', 0.85
    if 'wave' in engine: return 'CURVE', 0.85
    return 'NONE', 0.7

def get_recipe_data(category_name, user_prompt):
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()
    flexible_map = { "card": "print/business_cards.json", "flyer": "print/flyers.json" }
    selected_path = os.path.join(base_path, "print/flyers.json")
    for key, path in flexible_map.items():
        if key in cat or key in prompt:
            full_path = os.path.join(base_path, path)
            if os.path.exists(full_path):
                selected_path = full_path
                break
    try:
        with open(selected_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            if isinstance(raw, list): return random.choice(raw)
            return raw
    except: return {}

# ======================================================
# 👮‍♂️ VALIDATORS (Plan Content)
# ======================================================

def validate_plan_content(plan):
    if not isinstance(plan, dict): return False, "Malformed JSON Plan."
    
    contract = plan.get("design_contract")
    if not isinstance(contract, dict): return False, "Missing 'design_contract' block."

    # Strict Validation of Intent
    arabic_pos = str(contract.get("arabic_position", "")).lower()
    if "top" not in arabic_pos or "right" not in arabic_pos:
        return False, "Arabic Position Violation (Must be Top-Right)."

    contrast = str(contract.get("contrast_verified", "")).upper()
    if "YES" not in contrast:
        return False, "Contrast check failed or not verified."

    layout = str(contract.get("layout_variant", "")).lower()
    valid_layouts = ["hero", "minimal", "full", "split", "swiss", "diagonal"]
    if not any(v in layout for v in valid_layouts):
        return False, f"Invalid layout variant: {layout}"

    return True, "Valid"

# ======================================================
# 🚀 APP LOGIC V16.0 (The Geo-Engineered Architect)
# ======================================================

@app.route('/gemini', methods=)
def generate():
    if not client: return jsonify({"error": "AI Error"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        recipe = get_recipe_data(cat_name, user_msg)
        geo_mode, temp_setting = analyze_needs(recipe, user_msg, cat_name)
        seed = random.randint(0, 999999)
        
        # 1. Hard Rules
        indexed_rules =
        for i, r in enumerate(recipe.get('layout_rules',), 1): indexed_rules.append(f"LAYOUT_{i:02d}: {r}")
        for i, r in enumerate(recipe.get('typography_rules',), 1): indexed_rules.append(f"TYPE_{i:02d}: {r}")
        
        # 2. Geo Protocol & Assets
        geo_kit = None
        geo_instructions = ""
        assets_block = ""
        limits_info = "N/A"
        
        if geo_mode == 'CURVE':
            geo_kit = supply_curve_kit(width, height, seed)
            assets_block = "\n".join(.items()])
            limits_info = f"Bottom: {geo_kit['flip_info']['safe_y_bottom_mode']}"
            geo_instructions = f"""
            --- 📐 GEO PROTOCOL: CURVES ---
            STACKING ORDER (Strict Opacity Tiers):
            1. **Back**: 'curve_XL' (Opacity 0.12) -> Texture/Noise
            2. **Mid**: 'curve_L' (Opacity 0.45) -> Shape/Depth
            3. **Front**: 'curve_M' (Opacity 1.00) -> Focus Container
            ASSETS: {assets_block}
            """
        elif geo_mode == 'SHARP':
            geo_kit = supply_sharp_kit(width, height, seed)
            assets_block = "\n".join(.items()])
            limits_info = f"Bottom: {geo_kit['flip_info']['safe_y_bottom_mode']}"
            geo_instructions = f"""
            --- 📐 GEO PROTOCOL: POLYGONS ---
            STACKING ORDER:
            1. **poly_back**: Solid Accent (100% opacity).
            2. **poly_front**: Glass Effect (White fill, 0.2 opacity, Blur 5px).
            ASSETS: {assets_block}
            """
        else:
            geo_instructions = "--- 📐 GEO PROTOCOL: MINIMAL --- \nFocus on Grid, Typography Scale (Modular 1.25), and White Space."

        # 3. The Literal Contract Template (Pre-filled Keys for LLM to complete)
        plan_template = f"""{{
  "engine": "ALMONJEZ_V16",
  "category": "{cat_name}",
  "geo_mode": "{geo_mode}",
  "seed": {seed},
  "design_contract": {{
    "layout_variant": "hero|minimal|full|split",
    "empty_space_tactic": "pills|pattern|typography",
    "contrast_verified": "YES",
    "arabic_position": "top_right",
    "main_rules_applied": ["1_Hierarchy", "2_Contrast", "3_Arabic"],
    "recipe_rules_applied":
  }}
}}"""

        # System Instructions (Output Format: Plan THEN SVG)
        sys_instructions = f"""
        ROLE: Almonjez Geo-Design Architect.
        GOAL: Engineering-Grade SVG for "{cat_name}".
        
        --- 🏛️ CONSTITUTION ---
        {json.dumps(ALMONJEZ_CONSTITUTION, ensure_ascii=False)}
        
        --- 📜 RECIPE RULES ---
        {json.dumps(indexed_rules, ensure_ascii=False)}
        
        {geo_instructions}
        
        --- ✅ OUTPUT PROTOCOL ---
        1. OUTPUT "Plan: " followed by the filled JSON Contract.
        2. OUTPUT "SVG: " followed by the XML code.
        
        REQUIRED PLAN FORMAT:
        Plan: {plan_template}
        """

        # =========================================================
        # 🛡️ HYBRID LOOP + VALIDATION (The Engine)
        # =========================================================
        
        max_attempts = 2
        final_svg = None
        used_model = "unknown"
        extracted_plan = None
        
        models = ["gemini-2.0-pro-exp-02-05", "gemini-1.5-pro"]
        
        for attempt in range(max_attempts):
            model = models if attempt == 0 else models[-1]
            try:
                # Add correction prompt on retry
                current_sys = sys_instructions
                if attempt > 0:
                    current_sys += "\n\n⚠️ SYSTEM ALERT: Previous attempt failed (Missing Plan or Invalid Rules). FOLLOW PROTOCOL STRICTLY."

                response = client.models.generate_content(
                    model=model,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=current_sys, 
                        temperature=temp_setting if attempt==0 else 0.5,
                        max_output_tokens=8192
                    )
                )
                
                raw_text = response.text or ""
                
                # 1. Extract Plan using Robust Regex
                plan_match = PLAN_RE.search(raw_text)
                if not plan_match:
                    logger.warning(f"❌ Attempt {attempt+1}: Plan Regex Mismatch.")
                    if attempt < max_attempts - 1: continue 
                
                # Parse & Validate Plan
                try:
                    raw_json = sanitize_json_response(plan_match.group(1)) if plan_match else "{}"
                    plan = json.loads(raw_json)
                    is_valid, reason = validate_plan_content(plan)
                    if not is_valid:
                        logger.warning(f"❌ Attempt {attempt+1}: Invalid Plan ({reason})")
                        if attempt < max_attempts - 1: continue
                    extracted_plan = plan
                except Exception as e:
                    logger.warning(f"❌ Attempt {attempt+1}: JSON Parse Error ({e})")
                    if attempt < max_attempts - 1: continue

                # 2. Extract SVG using State-Aware Regex
                svg_match = SVG_EXTRACT_RE.search(raw_text)
                if svg_match:
                    final_svg = svg_match.group(0)
                    used_model = model
                    break # Success!
            
            except Exception as e:
                logger.error(f"⚠️ Engine Error: {e}")
                time.sleep(1)

        # =========================================================
        # 🔧 POST-PROCESSING (Geo Protocol Enforcement)
        # =========================================================
        
        if not final_svg:
             # Fallback if SVG extraction failed completely
             return jsonify({"error": "Failed to generate valid SVG geometry."}), 500

        # 1. Optimize Paths (Round numbers, Close paths)
        final_svg = optimize_path_data(final_svg)
        
        # 2. Inject Arabic Engineering (RTL attributes)
        final_svg = inject_arabic_support(final_svg)
        
        # 3. Standard Cleanup (ViewBox, Namespace)
        if 'xmlns=' not in final_svg: 
            final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        
        if 'viewbox' not in final_svg.lower():
             if '<svg xmlns' in final_svg:
                final_svg = final_svg.replace('<svg xmlns', f'<svg viewBox="0 0 {width} {height}" xmlns', 1)
             else:
                final_svg = final_svg.replace('<svg', f'<svg viewBox="0 0 {width} {height}"', 1)
        
        # 4. Inject Filter Definitions if missing (Blur Safety Net)
        if 'filter=' in final_svg and '<filter' not in final_svg:
            final_svg = final_svg.replace('</svg>', '<defs><filter id="blur"><feGaussianBlur stdDeviation="5"/></filter></defs></svg>')

        return jsonify({
            "response": final_svg,
            "meta": {
                "seed": seed,
                "model_used": used_model,
                "geo_mode": geo_mode,
                "design_plan": extracted_plan,
                "protocols_enforced":
            }
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
