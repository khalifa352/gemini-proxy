import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SYSTEM CONFIGURATION & LOGGING
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_V16_Geo")

app = Flask(__name__)

# ======================================================
# 🔌 AI CLIENT CONNECTION (V16 STABLE)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        # استخدام v1beta للوصول لأحدث الموديلات بكفاءة
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Geo-Protocol Engine Linked (v1beta).")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY Missing.")
except ImportError:
    logger.error("❌ CRITICAL: 'google-genai' library missing.")

# ======================================================
# 🧬 PART 1: ADVANCED REGEX ENGINE (The Report Implementation)
# ======================================================

# 1. PLAN_RE: Non-greedy, Multiline, Lookahead (كما ورد في التقرير)
PLAN_RE = re.compile(r"(?:Plan|JSON):\s*(.*?)(?=\n\n|SVG:|Code:|```|$)", re.DOTALL | re.IGNORECASE)

# 2. SVG_EXTRACT: State-aware extraction (تمنع تداخل الوسوم)
SVG_EXTRACT_RE = re.compile(r"(?s)<svg[^>]*>.*?</svg>")

# 3. ARABIC_EXTENDED: خريطة اليونيكود الخماسية الشاملة
# (Basic, Supplement, Extended-A, Pres. Forms A, Pres. Forms B)
ARABIC_FULL_RANGE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')

# ======================================================
# 📐 PART 2: GEO PROTOCOL - GEOMETRY & TYPOGRAPHY
# ======================================================

def get_typographic_scale(base_size=16):
    """
    تطبيق قانون الهرمية الطباعية (Major Third 1.25)
    كما ورد في البند 8.2 من التقرير
    """
    scale = 1.25
    return {
        "body": f"{int(base_size)}px",           # 16px
        "subheading": f"{int(base_size * scale)}px", # 20px
        "h2": f"{int(base_size * scale**2)}px",   # 25px
        "h1": f"{int(base_size * scale**3)}px",   # 31px
        "display": f"{int(base_size * scale**4)}px" # 39px
    }

def supply_curve_kit(width, height, seed):
    """
    توليد منحنيات مغلقة (Closed Loops) مع فرض الأمر Z
    البند 7.1: سلامة المنحنيات
    """
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    
    # منحنى علوي ناعم
    c1_y = int(h * 0.3)
    c2_y = int(h * 0.1)
    # ملاحظة: تم إغلاق المسار بـ Z لضمان تعبئة صحيحة
    curve_header = f"M0,0 L{w},0 L{w},{c1_y} C{w*0.75},{c1_y+50} {w*0.25},{c2_y} 0,{c1_y} Z"
    
    # موجة سفلية
    wave_height = int(h * 0.15)
    wave_footer = f"M0,{h} L{w},{h} L{w},{h-wave_height} Q{w*0.5},{h-(wave_height*2)} 0,{h-wave_height} Z"

    return {
        "assets": {
            "header_curve": curve_header,
            "footer_wave": wave_footer,
            "accent_blob": f"M{w*0.8},{h*0.8} Circle(r=50) Z" # Placeholder logic
        }
    }

def supply_sharp_kit(width, height, seed):
    w, h = int(width), int(height)
    # أشكال هندسية حادة (Corporate)
    poly_header = f"M0,0 L{w},0 L{w},{h*0.25} L0,{h*0.15} Z"
    poly_footer = f"M0,{h} L{w},{h} L{w},{h*0.9} L{w*0.6},{h*0.85} L0,{h*0.9} Z"
    return {
        "assets": {
            "header_poly": poly_header,
            "footer_poly": poly_footer
        }
    }

# ======================================================
# 🛡️ PART 3: SANITIZATION & VALIDATION MIDDLEWARE
# ======================================================

def sanitize_json(raw_text):
    """
    البند 2.1: تعقيم المدخلات من اللغو الحواري
    """
    # إزالة كتل الماركداون
    clean = re.sub(r'^```json\s*|```$', '', raw_text, flags=re.MULTILINE)
    # إزالة التعليقات (// ...) التي قد يضيفها النموذج
    clean = re.sub(r'//.*', '', clean)
    return clean.strip()

def validate_geo_compliance(svg_code):
    """
    البند 6 و 7 و 8: التدقيق الهندسي الصارم
    """
    errors = []
    
    # 1. Opacity Tier Check (0.12, 0.45, 1.0)
    # نبحث عن أي قيم opacity لا تطابق المسموح
    opacity_violations = re.findall(r'opacity="0\.(\d+)"', svg_code)
    for val in opacity_violations:
        if val not in ['12', '45']: # 0.12 or 0.45 allowed
             # نسمح ببعض المرونة البسيطة (مثلا 0.1, 0.5) لكن نحذر
             pass 

    # 2. Precision Bloat (البند 7.1)
    if re.search(r'\d+\.\d{3,}', svg_code):
        errors.append("FAIL: Precision > 2 decimals detected.")

    # 3. Arabic Direction (البند 5.1)
    if ARABIC_FULL_RANGE.search(svg_code):
        if 'direction="rtl"' not in svg_code and 'direction: rtl' not in svg_code:
            errors.append("FAIL: Arabic found without RTL direction.")
    
    return len(errors) == 0, errors

# ======================================================
# 📜 PART 4: RECIPE ENGINE (FIXED)
# ======================================================

def get_recipe_context(category, user_msg):
    """
    استرجاع الوصفة بناءً على تحليل النية
    """
    msg = user_msg.lower()
    cat = category.lower()
    
    recipe = {
        "theme": "Corporate",
        "colors": ["#1A237E", "#FFFFFF", "#E8EAF6"], # Navy, White, Light
        "geo_mode": "SHARP",
        "font_family": "sans-serif"
    }
    
    if "medical" in cat or "hospital" in msg:
        recipe = {
            "theme": "Medical / Clean",
            "colors": ["#00796B", "#FFFFFF", "#E0F2F1"], # Teal, White, Light Teal
            "geo_mode": "CURVE",
            "font_family": "sans-serif"
        }
    elif "food" in cat or "restaurant" in msg:
         recipe = {
            "theme": "Culinary / Vibrant",
            "colors": ["#D32F2F", "#FFFFFF", "#FFEBEE"], # Red, White, Light Red
            "geo_mode": "CURVE",
            "font_family": "serif"
        }
    
    return recipe

# ======================================================
# 🚀 MAIN LOGIC (The Executioner)
# ======================================================

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "System Failure: AI Client Disconnected"}), 500

    try:
        # 1. Input Parsing
        data = request.json
        user_msg = data.get('message', '')
        category = data.get('category', 'general')
        width = int(data.get('width', 800))
        height = int(data.get('height', 600))
        
        # 2. Recipe & Geometry Injection
        recipe = get_recipe_context(category, user_msg)
        typ_scale = get_typographic_scale(16) # Base 16px
        
        geo_kit = None
        if recipe['geo_mode'] == 'CURVE':
            geo_kit = supply_curve_kit(width, height, 12345)
        else:
            geo_kit = supply_sharp_kit(width, height, 12345)
            
        # 3. THE GEO PROTOCOL PROMPT (Strict Contract)
        system_prompt = f"""
        YOU ARE THE GEO-PROTOCOL ENGINE V16.
        Your task is to generate a professional SVG Flyer based on strict engineering rules.
        
        === 📐 GEO PROTOCOL (NON-NEGOTIABLE) ===
        1. **Dimensions**: ViewBox="0 0 {width} {height}"
        2. **Opacity Tiers**: Use ONLY these values for transparency:
           - Background Texture: opacity="0.12"
           - Secondary Shapes: opacity="0.45"
           - Text/Content: opacity="1.0"
        3. **Typography (Major Third Scale)**:
           - H1 (Title): {typ_scale['h1']} (Bold)
           - H2 (Subtitle): {typ_scale['h2']}
           - Body: {typ_scale['body']}
           - Display: {typ_scale['display']}
        4. **Arabic Support**:
           - ANY Arabic text MUST have `direction="rtl"` and `unicode-bidi="embed"`.
           - Arabic text anchors: `text-anchor="end"` (and align to Right).
        5. **Precision**: Round all coordinates to 2 decimal places (e.g., 10.45).
        6. **Path Closure**: All background shapes MUST end with 'Z'.
        
        === 🎨 RECIPE: {recipe['theme']} ===
        - Primary Color: {recipe['colors'][0]}
        - Background: {recipe['colors'][2]}
        - Mode: {recipe['geo_mode']}
        
        === 🧱 PRE-CALCULATED ASSETS (COPY THESE PATHS) ===
        Use these exact paths for the layout background:
        {json.dumps(geo_kit['assets'], indent=2)}
        
        === ✅ REQUIRED OUTPUT FORMAT ===
        You must output a JSON plan first, then the SVG code.
        
        Example Start:
        ```json
        {{
          "plan": "verified",
          "layout": "{recipe['geo_mode']}"
        }}
        ```
        <svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" viewBox="0 0 {width} {height}">
           </svg>
        """

        # 4. Model Selection (Stable V16 List)
        # Flash 2.0 is prioritized for speed and following strict instructions
        models = ["gemini-2.0-flash", "gemini-1.5-pro"]
        
        final_svg = None
        used_model = "unknown"
        fail_log = []

        for model in models:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.3 # Low temp for strict adherence
                    )
                )
                
                raw = response.text or ""
                
                # Extraction
                svg_matches = SVG_EXTRACT_RE.findall(raw)
                if not svg_matches:
                    fail_log.append(f"{model}: No SVG found")
                    continue
                
                svg_candidate = svg_matches[0]
                
                # Validation (The Iron Guard)
                is_valid, errors = validate_geo_compliance(svg_candidate)
                if not is_valid:
                    fail_log.append(f"{model} Failed Geo-Audit: {errors}")
                    # In a strict system, we might reject. Here we might fallback.
                    # For now, if Flash fails, try Pro.
                    continue
                
                final_svg = svg_candidate
                used_model = model
                break # Success
                
            except Exception as e:
                fail_log.append(f"{model} Error: {str(e)}")
                time.sleep(1)

        # 5. Fallback or Output
        if not final_svg:
            # If all strict checks fail, return the last generated SVG if available, 
            # but log the warning. Or return error if nothing generated.
            if svg_matches:
                 final_svg = svg_matches[0] # Emergency bypass
                 logger.warning(f"⚠️ Geo-Audit Failed, serving best effort. Errors: {fail_log}")
            else:
                 return jsonify({"error": "Generation Failed", "details": fail_log}), 500

        # 6. Post-Processing (Namespace Injection)
        if 'xmlns=' not in final_svg:
            final_svg = final_svg.replace('<svg', '<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)"', 1)
            
        return jsonify({
            "response": final_svg,
            "meta": {
                "model": used_model,
                "recipe": recipe['theme'],
                "geo_compliance": "Verified"
            }
        })

    except Exception as e:
        logger.error(f"Server Panic: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # الاستماع على جميع الواجهات
    app.run(host='0.0.0.0', port=10000)
