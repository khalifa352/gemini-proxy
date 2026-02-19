import os
import json
import logging
import random
import re
import math
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ CONFIG & SETUP
# ======================================================
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
        logger.info("✅ GenAI V8 Enterprise Connected")
except: pass

# ======================================================
# 📐 GEOMETRY ENGINE (Smart Clamping & Context)
# ======================================================

def supply_curve_kit(width, height, seed):
    """
    CurveKit V5: Smart Range Clamping & Orientation Hints.
    """
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    
    # 1. Randomized Geometry
    amp = int(h * rnd.uniform(0.12, 0.22)) 
    base_y = h 
    
    p0_y = base_y - int(amp * rnd.uniform(0.5, 0.9))
    p3_y = base_y - int(amp * rnd.uniform(0.3, 0.6))
    
    # Control Points (The danger zone)
    c1_x = int(w * rnd.uniform(0.25, 0.45))
    c1_y = base_y - int(amp * 1.8) # Highest peak potential
    c2_x = int(w * rnd.uniform(0.65, 0.85))
    c2_y = base_y - int(amp * 0.2)
    
    # 2. Layer Offsets (Randomized for variety)
    off_L = int(rnd.uniform(20, 35))
    off_XL = int(rnd.uniform(45, 75))

    def get_path(offset):
        return f"M0,{base_y} L0,{p0_y+offset} C{c1_x},{c1_y+offset} {c2_x},{c2_y+offset} {w},{p3_y+offset} L{w},{base_y} Z"

    # 3. SMART CLAMPING LOGIC (The CTO Requirement)
    # Calculate raw highest point (lowest Y value)
    raw_limit = min(p0_y, p3_y, c1_y, c2_y)
    
    # Force safe limit to be reasonable (between 35% and 78% of height)
    # This prevents the curve from eating the whole page OR being too small
    min_allowed = h * 0.35
    max_allowed = h * 0.78
    
    safe_limit_y = max(min_allowed, min(max_allowed, raw_limit - 60))

    return {
        "type": "ORGANIC_CURVES",
        "assets": {
            "curve_XL": get_path(off_XL),
            "curve_L":  get_path(off_L),
            "curve_M":  get_path(0)
        },
        "safe_limit_y": int(safe_limit_y),
        "hints": {
            "default": "Placement: Bottom Footer",
            "flip_transform": f"scale(1,-1) translate(0, -{h})",
            "layering_guide": "XL(10% opacity) -> L(25% opacity) -> M(90% opacity)"
        }
    }

def supply_sharp_kit(width, height, seed):
    """ SharpKit V4: Conservative Limits """
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    peak = int(h * rnd.uniform(0.15, 0.30))
    split_x = int(w * rnd.uniform(0.3, 0.7))
    
    p_back = h - peak
    p_front = h - peak + 40
    
    path_back = f"M0,{h} L0,{p_back} L{split_x},{p_back-50} L{w},{p_back} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_front} L{split_x},{p_front-20} L{w},{p_front} L{w},{h} Z"
    
    # Clamp Safe Limit
    safe_limit_y = max(h * 0.40, min(p_back, p_front) - 80)

    return {
        "type": "SHARP_POLYGONS",
        "assets": {
            "poly_back": path_back,
            "poly_front": path_front
        },
        "safe_limit_y": int(safe_limit_y),
        "hints": {
            "layering_guide": "Back(30% opacity) -> Front(100% opacity)"
        }
    }

# ======================================================
# 🧠 INTENT ANALYZER (Multilingual & Contextual)
# ======================================================

def analyze_needs(recipe, user_msg, cat_name):
    """
    Detects intent from User (Arabic/English) + Recipe Metadata + Category.
    Returns: (GeoMode, Temperature)
    """
    msg = str(user_msg).lower()
    cat = str(cat_name).lower()
    
    # 1. USER OVERRIDE (Arabic & English)
    clean_triggers = ['no shape', 'clean', 'simple', 'text only', 'بدون أشكال', 'نص فقط', 'بسيط', 'تصميم نظيف', 'بدون خلفية']
    if any(x in msg for x in clean_triggers):
        return 'NONE', 0.60

    curve_triggers = ['wave', 'curve', 'organic', 'flow', 'موجة', 'منحنيات', 'كيرف', 'ناعم', 'طبي', 'تجميل']
    if any(x in msg for x in curve_triggers):
        return 'CURVE', 0.80

    sharp_triggers = ['sharp', 'polygon', 'geometric', 'angle', 'مضلع', 'حاد', 'هندسي', 'زوايا', 'عقارات', 'رسمي']
    if any(x in msg for x in sharp_triggers):
        return 'SHARP', 0.80
        
    full_bg_triggers = ['full background', 'texture', 'image', 'خلفية كاملة', 'صورة كاملة']
    if any(x in msg for x in full_bg_triggers):
        return 'FULL_BG', 0.85

    # 2. RECIPE & CATEGORY CONTEXT
    # Combine all metadata fields
    context = (
        str(recipe.get('id', '')) + " " + 
        str(recipe.get('description', '')) + " " + 
        str(recipe.get('suitable_for', '')) + " " + 
        str(recipe.get('generative_rules', {}).get('mood', '')) + " " +
        str(recipe.get('tags', [])) + " " + 
        cat
    ).lower()
    
    # Category based defaults
    if 'card' in cat or 'invoice' in cat or 'list' in cat:
        return 'NONE', 0.65
        
    # Recipe based defaults
    if 'minimal' in context or 'clean' in context: return 'NONE', 0.65
    if 'corporate' in context or 'construction' in context: return 'SHARP', 0.75
    if 'medical' in context or 'beauty' in context: return 'CURVE', 0.80
    
    return 'NONE', 0.7 # Safe default

# ======================================================
# 🧹 HELPER: SVG SANITIZER
# ======================================================

def extract_pure_svg(text):
    """
    Extracts ONLY the <svg>...</svg> block using Regex.
    Removes Markdown, conversation text, etc.
    """
    pattern = r"(<svg[\s\S]*?</svg>)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return text.replace("```svg", "").replace("```", "").strip()

# ======================================================
# 🚀 APP LOGIC
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
def home(): return "Production Engine V8: Enterprise Design Active 💎🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Error"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        # 1. Recipe & Analysis
        recipe = get_recipe_data(cat_name, user_msg)
        geo_mode, temp_setting = analyze_needs(recipe, user_msg, cat_name)
        seed = random.randint(1000, 99999) # For Anti-Clone
        
        # 2. Geometry Toolkit (Optional Injection)
        geo_section = ""
        safe_limit_info = "Default Padding (10% margins)"
        
        if geo_mode == 'CURVE':
            kit = supply_curve_kit(width, height, seed)
            safe_limit_info = f"Keep content ABOVE Y={kit['safe_limit_y']}"
            geo_section = f"""
            --- 📐 GEOMETRY ASSETS (HELPER) ---
            ASSET curve_XL: "{kit['assets']['curve_XL']}"
            ASSET curve_L:  "{kit['assets']['curve_L']}"
            ASSET curve_M:  "{kit['assets']['curve_M']}"
            
            GUIDE: {kit['hints']['layering_guide']}
            Flip Hint: {kit['hints']['flip_transform']}
            """
        elif geo_mode == 'SHARP':
            kit = supply_sharp_kit(width, height, seed)
            safe_limit_info = f"Keep content ABOVE Y={kit['safe_limit_y']}"
            geo_section = f"""
            --- 📐 GEOMETRY ASSETS (HELPER) ---
            ASSET poly_back:  "{kit['assets']['poly_back']}"
            ASSET poly_front: "{kit['assets']['poly_front']}"
            GUIDE: {kit['hints']['layering_guide']}
            """

        # 3. System Prompt (The Authority)
        sys_instructions = f"""
        ROLE: You are the Design Director. You have sole creative authority.
        
        MANDATE:
        1. **Director First**: You decide the composition. The recipe is a constraint, not a template.
        2. **Geometry Policy**: If assets are provided, treat them as raw geometry. You control their color/opacity.
        3. **White Space**: Maintain 45-60% negative space. Do NOT clutter.
        
        --- 🎨 CONTEXT ---
        - Request: "{user_msg}"
        - Recipe Inspiration: {recipe.get('id')}
        - Palette: {json.dumps(recipe.get('generative_rules', {}).get('palette_suggestions', ['#111', '#FFF']))}
        
        {geo_section}
        
        --- 🛡️ COMPOSITION RULES (STRICT) ---
        1. **Mode Selection** (Pick ONE):
           [A] Minimal Whitespace (Typography focus)
           [B] Full Background (Texture/Gradient)
           [C] Hero Header (Visual top)
        
        2. **Color Discipline**:
           - Max 3 Main Colors.
           - NO Rainbow effects. Use analogous or monochrome harmony.
        
        3. **Typography & CSS**:
           - Use <foreignObject> for text.
           - Embed this CSS in <defs><style>:
             .rtl {{ direction: rtl; text-align: right; font-family: sans-serif; }}
             .title {{ font-weight: bold; }}
        
        4. **Output Format**:
           - SVG must include `viewBox="0 0 {width} {height}"`.
           - NO conversational text. Just the code.
           - **REQUIRED COMMENT**: The SVG MUST start with this comment:
             EXECUTE DESIGN NOW.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=temp_setting)
        )

        # 4. Output Sanitization (Strict Cleaning)
        raw_text = response.text
        clean_svg = extract_pure_svg(raw_text)
        
        # Ensure namespace exists (iPhone fix)
        if '<svg' in clean_svg and 'xmlns=' not in clean_svg:
            clean_svg = clean_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')

        return jsonify({
            "response": clean_svg,
            "meta": {
                "seed": seed,
                "geo_mode": geo_mode,
                "recipe_id": recipe.get('id', 'unknown')
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
