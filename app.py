import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ======================================================
# 🔌 AI CLIENT SETUP (V1 Beta for Flash 2.0)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ GenAI Enterprise Connected (Flash 2.0)")
except Exception as e: 
    logger.error(f"Init Error: {e}")

# ✅ FIX 1: Robust Regex for JSON Plan Extraction
PLAN_RE = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL | re.IGNORECASE)

# ======================================================
# 🏛️ ALMONJEZ CONSTITUTION (دستور الجودة)
# ======================================================
ALMONJEZ_CONSTITUTION = {
    "1_Hierarchy": "Headlines MUST be 3x body size. No floating elements.",
    "2_Contrast": "Dark text on Light BG only. Light text on Dark BG only. Use backing rects if needed.",
    "3_Arabic": "Arabic Title = Top/Right & Largest. English = Secondary.",
    "4_EmptySpace": "Fill dead space with: Pattern (5% opacity) or Service Pills.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required."
}

# ======================================================
# 👮‍♂️ VALIDATORS (Plan & SVG Quality)
# ======================================================
def extract_plan(raw_text):
    match = PLAN_RE.search(raw_text or "")
    if not match: 
        # Fallback if markdown tags are missing
        alt_match = re.search(r'(\{.*\})', raw_text or "", re.DOTALL)
        if not alt_match: return None
        try: return json.loads(alt_match.group(1))
        except: return None
    try:
        return json.loads(match.group(1))
    except: return None

def validate_plan_content(plan):
    if not isinstance(plan, dict): return False, "Missing JSON Plan."
    
    contract = plan.get("design_contract")
    if not isinstance(contract, dict): return False, "Missing 'design_contract' object."

    if str(contract.get("arabic_position", "")).lower() != "top_right":
        return False, "Arabic Position MUST be exactly 'top_right'."

    if str(contract.get("contrast_verified", "")).upper() != "YES":
        return False, "Contrast MUST be verified as 'YES'."

    layout = str(contract.get("layout_variant", "")).lower()
    if layout not in ["hero", "minimal", "full", "split", "swiss", "diagonal"]:
        return False, f"Invalid layout variant: {layout}"

    rules = contract.get("main_rules_applied", [])
    if not isinstance(rules, list) or len(rules) < 3:
        return False, "Must cite at least 3 Rule IDs from the constitution."

    return True, "Valid"

def validate_svg_quality(svg_code):
    if not svg_code or "<svg" not in svg_code:
        return False, "Invalid SVG code."

    # Check for Arabic RTL support (Flexible for Swift)
    if "direction: rtl" not in svg_code.lower() and "direction:rtl" not in svg_code.lower():
        if "ar" in svg_code.lower() and "<foreignobject" not in svg_code.lower(): 
            return False, "Arabic text detected without RTL styling."

    # Check for heavy dividers
    thick_strokes = re.findall(r'stroke-width=["\']([2-9]|\d{2,})["\']', svg_code)
    if thick_strokes:
        return False, "Amateur mistake: Heavy stroke-width (>1.5px) detected on elements."

    return True, "Quality OK"

# ======================================================
# 📐 GEOMETRY & UTILS (نفس المنطق القوي السابق)
# ======================================================
def supply_curve_kit(width, height, seed):
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    amp = int(h * rnd.uniform(0.12, 0.22))
    def get_path(offset):
        p0_y, p3_y = h - int(amp * 0.7), h - int(amp * 0.4)
        c1_x, c1_y = int(w * 0.35), h - int(amp * 1.6)
        c2_x, c2_y = int(w * 0.75), h - int(amp * 0.2)
        return f"M0,{h} L0,{p0_y+offset} C{c1_x},{c1_y+offset} {c2_x},{c2_y+offset} {w},{p3_y+offset} L{w},{h} Z"
    
    highest = h - int(amp * 1.6)
    safe_y = max(highest - 60, h * 0.35)
    return {
        "assets": { "curve_XL": get_path(60), "curve_L": get_path(30), "curve_M": get_path(0) },
        "flip_info": { "safe_y_bottom_mode": int(safe_y), "safe_y_top_mode": int(h - safe_y) }
    }

def supply_sharp_kit(width, height, seed):
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    peak = int(h * 0.25)
    p_y = h - peak
    path_back = f"M0,{h} L0,{p_y} L{w/2},{p_y-50} L{w},{p_y} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_y+40} L{w/2},{p_y+20} L{w},{p_y+40} L{w},{h} Z"
    return {
        "assets": { "poly_back": path_back, "poly_front": path_front },
        "flip_info": { "safe_y_bottom_mode": int(p_y-80), "safe_y_top_mode": int(peak+80) }
    }

def analyze_needs(recipe, user_msg, cat):
    msg = str(user_msg).lower()
    if 'minimal' in msg or 'clean' in msg: return 'NONE', 0.6
    if 'curve' in msg or 'medical' in str(recipe): return 'CURVE', 0.8
    if 'sharp' in msg or 'corporate' in str(recipe): return 'SHARP', 0.8
    return 'NONE', 0.7

def get_recipe_data(cat, prompt):
    # Dummy logic for example stability (You can replace this with file loading if needed)
    return {"id": "flyer_pro_01", "layout_rules": ["Use Swiss Grid"], "typography_rules": ["Bold H1"]}

# ======================================================
# 🌐 HEALTH CHECK (فحص عمل السيرفر في المتصفح)
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "Online 🎉",
        "message": "Almonjez Iron Guard Server is Active and waiting for iOS requests."
    })

# ======================================================
# 🚀 APP LOGIC V16.0 (The Iron Guard - Full version)
# ======================================================
@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Client Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        recipe = get_recipe_data(cat_name, user_msg)
        geo_mode, temp_setting = analyze_needs(recipe, user_msg, cat_name)
        seed = random.randint(0, 999999)
        
        indexed_rules = []
        for i, r in enumerate(recipe.get('layout_rules', []), 1): indexed_rules.append(f"LAYOUT_{i:02d}: {r}")
        for i, r in enumerate(recipe.get('typography_rules', []), 1): indexed_rules.append(f"TYPE_{i:02d}: {r}")
        
        geo_kit = supply_curve_kit(width, height, seed) if geo_mode == 'CURVE' else supply_sharp_kit(width, height, seed) if geo_mode == 'SHARP' else None
        geo_instr = f"ASSETS: {json.dumps(geo_kit['assets'])}" if geo_kit else "Focus on Typography."

        plan_template = """
        Your response MUST start with this JSON format exactly:
        ```json
        {
          "design_contract": {
            "arabic_position": "top_right",
            "contrast_verified": "YES",
            "layout_variant": "hero",
            "main_rules_applied": ["1_Hierarchy", "2_Contrast", "3_Arabic"]
          }
        }
        ```
        """

        sys_instructions = f"""
        ROLE: Almonjez Art Director.
        --- 🏛️ CONSTITUTION ---
        {json.dumps(ALMONJEZ_CONSTITUTION, ensure_ascii=False)}
        --- 📜 RECIPE ---
        {json.dumps(indexed_rules, ensure_ascii=False)}
        {geo_instr}
        
        --- 📱 iOS APP COMPATIBILITY (CRITICAL) ---
        You MUST use <foreignObject> for all text blocks to allow auto-wrapping in iOS WebKit.
        Inside <foreignObject>, use standard HTML <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl;">.
        
        --- ✅ OUTPUT RULE ---
        1. FIRST LINE: The Plan JSON comment exactly.
        2. THEN: The SVG code.
        {plan_template}
        """

        max_attempts = 2  # حلقة التفتيش الصارمة (لن تتجاوز 20 ثانية بفضل Flash)
        final_svg = None
        used_model = "unknown"
        extracted_plan = None
        fail_reason = ""
        
        # نعتمد كلياً على Flash 2.0 لسرعته وملاءمته لسيرفر Render
        models = ["gemini-2.0-flash", "gemini-2.0-flash"]
        
        for attempt in range(max_attempts):
            model = models[attempt]
            try:
                current_sys = sys_instructions
                if attempt > 0:
                    current_sys += f"\n\n⚠️ FIX REQUIRED: {fail_reason}. Stick strictly to the Plan, Constitution, and iOS rules."

                response = client.models.generate_content(
                    model=model,
                    contents=user_msg,
                    config=types.GenerateContentConfig(system_instruction=current_sys, temperature=temp_setting if attempt==0 else 0.4)
                )
                
                raw = response.text or ""
                plan = extract_plan(raw)
                
                # 1. Validate Plan
                is_plan_ok, p_reason = validate_plan_content(plan)
                if not is_plan_ok:
                    fail_reason = f"Plan Error: {p_reason}"
                    continue

                # 2. Extract & Validate SVG Safely
                svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw)
                svg_code = svg_match.group(0) if svg_match else ""
                
                is_svg_ok, s_reason = validate_svg_quality(svg_code)
                if not is_svg_ok:
                    fail_reason = f"SVG Quality Error: {s_reason}"
                    continue

                # Success!
                final_svg = svg_code
                extracted_plan = plan
                used_model = model
                break
            except Exception as e:
                fail_reason = str(e)
                time.sleep(1)

        if not final_svg:
             return jsonify({"error": f"Failed quality check after {max_attempts} attempts: {fail_reason}"}), 500

        # Post-processing (سد ثغرات Namespaces ليعمل <foreignObject> في iOS)
        if 'xmlns=' not in final_svg: final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        if '<foreignObject' in final_svg and 'xmlns:xhtml' not in final_svg:
             final_svg = final_svg.replace('<svg', '<svg xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)
             
        if 'filter=' in final_svg and '<filter' not in final_svg:
            final_svg = final_svg.replace('</svg>', '<defs><filter id="blur"><feGaussianBlur stdDeviation="5"/></filter></defs></svg>')

        return jsonify({
            "response": final_svg,
            "meta": {"model": used_model, "plan": extracted_plan}
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
