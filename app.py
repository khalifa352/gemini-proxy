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
# 🛠️ HELPER FUNCTIONS
# ======================================================

def _clamp(val, min_v, max_v):
    return max(min_v, min(val, max_v))

# ======================================================
# 📐 GEOMETRY ENGINE (V9.2 Stable)
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

    highest_point = min(p0_y, p3_y, c1_y, c2_y)
    safe_limit_y = _clamp(highest_point - 60, h * 0.35, h * 0.78)

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
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    peak = int(h * rnd.uniform(0.15, 0.30))
    split_x = int(w * rnd.uniform(0.3, 0.7))
    
    p_back_y = h - peak
    p_front_y = h - peak + 40
    
    path_back = f"M0,{h} L0,{p_back_y} L{split_x},{p_back_y-50} L{w},{p_back_y} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_front_y} L{split_x},{p_front_y-20} L{w},{p_front_y} L{w},{h} Z"
    
    raw_limit = min(p_back_y, p_front_y) - 80
    safe_limit_y = _clamp(raw_limit, h * 0.40, h * 0.80)

    return {
        "type": "SHARP_POLYGONS",
        "assets": {
            "poly_back": path_back,
            "poly_front": path_front
        },
        "safe_limit_y": int(safe_limit_y),
        "flip_info": {
            "safe_y_bottom_mode": int(safe_limit_y),
            "safe_y_top_mode": int(h - safe_limit_y)
        }
    }

# ======================================================
# 🧠 INTELLIGENCE V9.2
# ======================================================

def analyze_needs(recipe, user_msg, category_name="general"):
    msg = str(user_msg).lower()
    cat = str(category_name).lower()
    
    recipe_text = " ".join([
        str(recipe.get('id', '')),
        str(recipe.get('tags', [])),
        str(recipe.get('description', '')),
        str(recipe.get('mood', '')),
        str(recipe.get('suitable_for', ''))
    ]).lower()

    clean_triggers = ['clean', 'text only', 'simple', 'minimal', 'بدون أشكال', 'تصميم نظيف', 'نص فقط', 'بسيط', 'هادئ']
    curve_triggers = ['wave', 'curve', 'organic', 'fluid', 'منحنيات', 'كيرف', 'تموج', 'ناعم', 'طبي']
    sharp_triggers = ['sharp', 'polygon', 'geometric', 'edge', 'مضلعات', 'هندسي', 'زوايا', 'حادة']
    full_bg_triggers = ['full background', 'texture', 'image', 'خلفية كاملة', 'صورة كاملة', 'فول باكقراوند', 'خلفية فل']

    if any(x in msg for x in clean_triggers): return 'NONE', 0.6
    
    if any(x in msg for x in full_bg_triggers):
        if 'corporate' in recipe_text or 'tech' in recipe_text or 'business' in recipe_text:
            return 'SHARP', 0.85
        return 'CURVE', 0.85 

    if any(x in msg for x in curve_triggers): return 'CURVE', 0.8
    if any(x in msg for x in sharp_triggers): return 'SHARP', 0.8
    
    if 'card' in cat: return 'NONE', 0.65
    if 'flyer' in cat and ('corporate' in recipe_text or 'business' in recipe_text): 
        return 'SHARP', 0.75

    engine = str(recipe.get('geometry_engine', 'none')).lower()
    if engine != 'none':
        if 'sharp' in engine or 'diagonal' in engine: return 'SHARP', 0.85
        if 'wave' in engine or 'curve' in engine: return 'CURVE', 0.85
    
    if 'minimal' in recipe_text: return 'NONE', 0.65
    if 'corporate' in recipe_text or 'tech' in recipe_text: return 'SHARP', 0.75
    if 'medical' in recipe_text or 'beauty' in recipe_text or 'food' in recipe_text: return 'CURVE', 0.8
    
    return 'NONE', 0.7

# ======================================================
# 🚀 APP LOGIC V9.2 (FINAL)
# ======================================================

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

@app.route('/')
def home(): return "Enterprise Engine V9.2: The Final Seal 🔒"

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
        
        # ✅ FIX 1: Robust Indexed Rules (Strings, Lists, Bools)
        indexed_rules = []
        
        for i, r in enumerate(recipe.get('layout_rules', []), 1):
            indexed_rules.append(f"LAYOUT_{i:02d}: {r}")
            
        for i, r in enumerate(recipe.get('typography_rules', []), 1):
            indexed_rules.append(f"TYPE_{i:02d}: {r}")
            
        # Handle Generative Rules (Strings & Lists & Bools)
        for k, v in recipe.get('generative_rules', {}).items():
            key_name = f"GEN_{k.upper()}"
            if isinstance(v, (str, int, float, bool)):
                indexed_rules.append(f"{key_name}: {v}")
            elif isinstance(v, list):
                # Ensure lists (like palette) are included properly
                indexed_rules.append(f"{key_name}: {json.dumps(v, ensure_ascii=False)}")

        # Distilled Context
        recipe_extract = {
            "id": recipe.get('id', 'unknown'),
            "description": recipe.get('description', 'Generic Design'),
            "mood_keywords": recipe.get('mood', 'Professional')
        }
        
        geo_kit = None
        geo_instructions = ""
        
        if geo_mode != 'NONE':
            if geo_mode == 'CURVE':
                geo_kit = supply_curve_kit(width, height, seed)
            else:
                geo_kit = supply_sharp_kit(width, height, seed)

            assets_block = "\n".join([f'ASSET {k}: "{v}"' for k, v in geo_kit['assets'].items()])
            
            limits_info = f"""
            - If placed at BOTTOM: Keep text ABOVE Y={geo_kit['flip_info']['safe_y_bottom_mode']}
            - If placed at TOP (flipped): Keep text BELOW Y={geo_kit['flip_info']['safe_y_top_mode']}
            """
            
            geo_instructions = f"""
            --- 📐 GEOMETRY CONSTITUTION ---
            1. **STRUCTURAL (Allowed):** You MAY use <rect> or <line> for grids, borders, or layout containers.
            2. **DECORATIVE (Restricted):** You MUST use the provided Python Assets below for any complex visual shapes.
               - DO NOT draw custom blobs/curves manually.
            
            Python Assets Provided:
            {assets_block}
            
            Safe Limits: {limits_info}
            """
        else:
            geo_instructions = """
            --- 📐 GEOMETRY CONSTITUTION ---
            1. **STRUCTURAL (Allowed):** Simple <rect>/<line> for layout structure only.
            2. **DECORATIVE (Forbidden):** NO decorative shapes, blobs, or complex paths. Focus on Typography.
            """

        # ✅ FIX 2: Define Literal Meta Template (Pre-filled by Server)
        meta_template = f""""""

        # System Instructions with Template Injection
        sys_instructions = f"""
        ROLE: Senior Art Director & SVG Technician.
        GOAL: Create a production-ready SVG for a "{cat_name}".
        
        --- 🎨 CONTEXT EXTRACT ---
        - Request: "{user_msg}"
        - Dimensions: {width}x{height}
        - Recipe Meta: {json.dumps(recipe_extract, ensure_ascii=False)}
        
        --- 📜 HARD RULES (BINDING CONTRACT) ---
        You MUST apply at least 3 rules from this list and cite their IDs in the JSON:
        {json.dumps(indexed_rules, ensure_ascii=False)}
        
        {geo_instructions}
        
        --- 🛡️ STRICT PRODUCTION PROTOCOLS ---
        
        A) **META PLANNING (MANDATORY)**
        Your FIRST line MUST be an SVG comment containing EXACTLY this JSON structure (fill values):
        
        {meta_template}
        
        RULE: The SVG MUST start with that comment, keep same keys, and 'main_rules_applied' MUST contain IDs from HARD RULES list above.
        
        B) **COMPOSITION MODES**
        - Minimal: High whitespace, typography-first.
        - Full: Full bleed background.
        - Hero: Split layout.
        
        C) **COLOR DISCIPLINE**
        - Use MAX 3 distinct colors + black/white.
        - Prefer monochrome/analogous harmony.
        
        D) **TECHNICAL HYGIENE**
        - ViewBox MUST be: viewBox="0 0 {width} {height}"
        - Put CSS in <style>.
        - Arabic: direction: rtl; text-align: right;
        - Use <foreignObject> for complex text.
        
        OUTPUT:
        Return ONLY valid SVG code. No extra text.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=temp_setting)
        )

        raw_text = response.text or ""
        
        # Extract SVG
        svg_output = raw_text
        start_tag = raw_text.find('<svg')
        end_tag = raw_text.rfind('</svg>')
        
        if start_tag != -1 and end_tag != -1:
            svg_output = raw_text[start_tag : end_tag + 6]
        else:
            svg_output = svg_output.replace("```svg", "").replace("```", "").strip()
        
        # Safe Namespace Injection
        if 'xmlns=' not in svg_output:
            svg_output = svg_output.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            
        # Robust Case-Insensitive ViewBox Check
        if 'viewbox' not in svg_output.lower():
            viewbox_str = f' viewBox="0 0 {width} {height}"'
            if '<svg xmlns' in svg_output:
                svg_output = svg_output.replace('<svg xmlns', f'<svg{viewbox_str} xmlns', 1)
            else:
                svg_output = svg_output.replace('<svg', f'<svg{viewbox_str}', 1)

        return jsonify({
            "response": svg_output,
            "meta": {
                "seed": seed,
                "geo_mode": geo_mode,
                "recipe_id": recipe.get('id', 'unknown'),
                "safe_limit_y": geo_kit['safe_limit_y'] if geo_kit else "N/A"
            }
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
