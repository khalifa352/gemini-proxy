import os
import json
import logging
import random
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
# 🏛️ GLOBAL DESIGN CONSTITUTION (الدستور العام)
# ======================================================
# هذه القوانين تطبق على جميع الوصفات لرفع الجودة فوراً
GLOBAL_CONSTITUTION = {
    "typography_contract": {
        "H1": "Must be > 2.5x body size, Heavy/Bold weight",
        "H2": "Must be uppercase or distinct color, max 1 line",
        "Body": "Readable contrast, max 65 chars per line",
        "CTA": "Must be a pill/button shape, not just text"
    },
    "layout_variants": [
        "Swiss Grid (Left Align)",
        "Split Screen (Hero Top / Details Bottom)",
        "Central Focus (Symmetrical)",
        "Diagonal Tension (Asymmetric)",
        "Editorial Sidebar"
    ],
    "missing_content_policy": [
        "IF text is short: Generate 3 'Service Pills' (e.g., 'Fast', 'Reliable', '24/7')",
        "IF background is empty: Add a large transparent watermark (opacity 0.05) or geometric pattern",
        "IF no subtitle: Generate a professional slogan based on context"
    ],
    "layering_rules": [
        "Background: Base Color",
        "Midground: Pattern/Texture (Low Opacity)",
        "Foreground: Content Cards + Shadows",
        "Overlay: CurveKit Assets (with Glow/Shadow effects)"
    ]
}

# ======================================================
# 📐 GEOMETRY ENGINE (Asset Provider)
# ======================================================

def supply_curve_kit(width, height, seed):
    # (نفس منطق التوليد السابق - مختصر هنا للتركيز على التغييرات)
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
        "assets": {
            "curve_XL": get_path(off_XL),
            "curve_L":  get_path(off_L),
            "curve_M":  get_path(0)
        },
        "safe_limit_y": int(safe_limit_y),
        "flip_info": {
            "safe_y_bottom_mode": int(safe_limit_y),
            "safe_y_top_mode": int(h - safe_limit_y)
        },
        "hint": "Assets are bottom-anchored. To flip to top: transform='scale(1,-1) translate(0,-height)'"
    }

def supply_sharp_kit(width, height, seed):
    # (نفس منطق التوليد السابق)
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
        "type": "SHARP_POLYGONS",
        "assets": { "poly_back": path_back, "poly_front": path_front },
        "safe_limit_y": int(safe_limit_y),
        "flip_info": { "safe_y_bottom_mode": int(safe_limit_y), "safe_y_top_mode": int(h - safe_limit_y) }
    }

# ======================================================
# 🧠 INTELLIGENCE (Upgraded Analysis)
# ======================================================

def analyze_needs(recipe, user_msg, category_name="general"):
    # (نفس المنطق القوي السابق)
    msg = str(user_msg).lower()
    cat = str(category_name).lower()
    recipe_text = str(recipe).lower()
    
    if 'card' in cat: return 'NONE', 0.65
    
    # Keyword analysis
    clean_kw = ['clean', 'text only', 'minimal', 'بدون أشكال']
    full_bg_kw = ['full background', 'texture', 'image', 'خلفية كاملة']
    
    if any(x in msg for x in clean_kw): return 'NONE', 0.6
    
    if any(x in msg for x in full_bg_kw):
        if 'corporate' in recipe_text: return 'SHARP', 0.85
        return 'CURVE', 0.85

    if 'curve' in msg or 'wave' in msg: return 'CURVE', 0.8
    if 'sharp' in msg or 'geometric' in msg: return 'SHARP', 0.8
    
    # Fallback to Recipe hints
    engine = str(recipe.get('geometry_engine', 'none')).lower()
    if 'sharp' in engine: return 'SHARP', 0.85
    if 'wave' in engine: return 'CURVE', 0.85
    
    return 'NONE', 0.7

# ======================================================
# 🚀 APP LOGIC V10.0
# ======================================================

def get_recipe_data(category_name, user_prompt):
    # (نفس كود جلب الملفات JSON)
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

@app.route('/gemini', methods=['POST'])
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
        
        # 1. Prepare Hard Rules (Indexed)
        indexed_rules = []
        for i, r in enumerate(recipe.get('layout_rules', []), 1): indexed_rules.append(f"LAYOUT_{i:02d}: {r}")
        for i, r in enumerate(recipe.get('typography_rules', []), 1): indexed_rules.append(f"TYPE_{i:02d}: {r}")
        for k, v in recipe.get('generative_rules', {}).items():
            key = f"GEN_{k.upper()}"
            val = json.dumps(v, ensure_ascii=False) if isinstance(v, list) else str(v)
            indexed_rules.append(f"{key}: {val}")

        # 2. Geometry & Assets
        geo_kit = None
        geo_instructions = ""
        assets_block = ""
        limits_info = "N/A"
        
        if geo_mode != 'NONE':
            if geo_mode == 'CURVE':
                geo_kit = supply_curve_kit(width, height, seed)
            else:
                geo_kit = supply_sharp_kit(width, height, seed)
            
            assets_block = "\n".join([f'ASSET {k}: "{v}"' for k, v in geo_kit['assets'].items()])
            limits_info = f"Bottom Limit: {geo_kit['flip_info']['safe_y_bottom_mode']} | Top Limit: {geo_kit['flip_info']['safe_y_top_mode']}"
            
            geo_instructions = f"""
            --- 📐 GEOMETRY & LAYERING ---
            You have powerful assets. Don't just place them; STYLE THEM.
            
            1. **Layering Requirement**:
               - Layer 1 (Back): 'curve_XL' at 10-20% opacity (Depth).
               - Layer 2 (Mid):  'curve_L' at 40-60% opacity (Accent).
               - Layer 3 (Front): 'curve_M' at 90-100% opacity (Main shape).
            
            2. **Effects**:
               - Add subtle drop-shadows to Layer 3.
               - Add a thin stroke (0.5px) to Layer 2 for definition.
            
            ASSETS:
            {assets_block}
            Safe Limits: {limits_info}
            """
        else:
            geo_instructions = "--- 📐 GEOMETRY: NONE --- \nFocus purely on Grid, Typography Scale, and Negative Space."

        # 3. The DESIGN PLAN Template (Injecting the Constitution)
        plan_template = f""""""

        # 4. The Director's System Instructions
        sys_instructions = f"""
        ROLE: Elite Design Director & SVG Architect.
        GOAL: Create a High-End, Professional SVG for "{cat_name}".
        
        --- 🎨 INPUT & CONTEXT ---
        - Request: "{user_msg}"
        - Dimensions: {width}x{height}
        - Base Recipe: {json.dumps(recipe.get('description',''), ensure_ascii=False)}
        
        --- 🏛️ GLOBAL DESIGN CONSTITUTION (NON-NEGOTIABLE) ---
        {json.dumps(GLOBAL_CONSTITUTION, ensure_ascii=False)}
        
        --- 📜 RECIPE HARD RULES ---
        You MUST apply at least 3 rules from here:
        {json.dumps(indexed_rules, ensure_ascii=False)}
        
        {geo_instructions}
        
        --- ⚠️ PROFESSIONALISM PROTOCOLS ---
        1. **Short Text Syndrome**: If the user text is short, you MUST generate filler content (Service Pills, Slogans, Watermarks) to balance the layout. Do NOT leave empty holes.
        2. **Visual Hierarchy**: Never make everything the same size. H1 must be huge. Details must be small.
        3. **Layout Variance**: Pick a specific layout variant (e.g., Split Screen, Swiss Grid) and stick to it.
        
        --- ✅ OUTPUT REQUIREMENT ---
        1. Start with the DESIGN PLAN comment (Exact JSON below).
        2. Follow with the valid SVG code.
        
        FIRST LINE MUST BE:
        {plan_template}
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=temp_setting)
        )

        # Output Cleaning
        raw_text = response.text or ""
        svg_output = raw_text
        start_tag = raw_text.find('<svg')
        end_tag = raw_text.rfind('</svg>')
        
        if start_tag != -1 and end_tag != -1:
            svg_output = raw_text[start_tag : end_tag + 6]
        else:
            svg_output = svg_output.replace("```svg", "").replace("```", "").strip()
            
        if 'xmlns=' not in svg_output:
            svg_output = svg_output.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        
        if 'viewbox' not in svg_output.lower():
             # Inject viewBox smartly
             if '<svg xmlns' in svg_output:
                svg_output = svg_output.replace('<svg xmlns', f'<svg viewBox="0 0 {width} {height}" xmlns', 1)
             else:
                svg_output = svg_output.replace('<svg', f'<svg viewBox="0 0 {width} {height}"', 1)

        return jsonify({
            "response": svg_output,
            "meta": {
                "seed": seed,
                "geo_mode": geo_mode,
                "recipe_id": recipe.get('id', 'unknown')
            }
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
