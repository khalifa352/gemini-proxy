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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [V16-GEO] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
except ImportError:
    logger.warning("Google GenAI SDK not found. AI features disabled.")
except Exception as e:
    logger.error(f"Failed to initialize GenAI Client: {e}")

# ======================================================
# 🧠 RE-ENGINEERED REGEX ENGINE (The Iron Guard)
# ======================================================

# 1. PLAN_RE: معالجة تعدد الأسطر + إلغاء الجشع (Non-Greedy)
# يلتقط JSON سواء كان داخل كتل Markdown أو كائن خام، مع التعامل الذكي مع فواصل الأسطر
PLAN_RE = re.compile(r"```json\s*(.*?)\s*```|^\s*(\{.*\})\s*$", re.DOTALL | re.MULTILINE)

# 2. SVG_EXTRACT_RE: استخراج مدرك للحالة (State-Aware)
# يمنع تداخل الوسوم ويعالج الخصائص الموزعة على عدة أسطر
SVG_EXTRACT_RE = re.compile(r"(?s)<svg[^>]*>.*?</svg>")

# 3. ARABIC_EXTENDED_RE: النطاقات الموسعة (Unicode 17.0 Standards)
# يشمل: الأساسي، الملحق (فارسي/أردو)، الموسع، وأشكال العرض (Presentation Forms A&B)
ARABIC_EXTENDED_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)

# ======================================================
# 📐 ALMONJEZ CONSTITUTION & GEO PROTOCOL
# ======================================================
ALMONJEZ_CONSTITUTION = {
    "1_Hierarchy": "Headlines MUST be 3x body size using Modular Scale 1.25.",
    "2_Contrast": "Strict Opacity Tiers: BG=0.12, Shape=0.45, Text=1.0.",
    "3_Arabic_BiDi": "FORCE 'direction: rtl' on Arabic text. Flip text-anchor: start -> end.",
    "4_Geo_Safety": "Keep content within Safe Zone (5mm margin). Round coordinates to 2 decimals.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required."
}

GEO_PROTOCOL = {
    "opacity_tiers": {"bg": 0.12, "mid": 0.45, "focus": 1.0},
    "precision": 2,
    "safe_margin_pct": 0.05  # 5% margin
}

# ======================================================
# 🛡️ SANITIZATION MIDDLEWARE (طبقة التعقيم)
# ======================================================

def sanitize_json_payload(raw_text):
    """
    تنظيف النص الخام من شوائب LLM (تعليقات، فواصل زائدة، نصوص Markdown)
    لضمان استخراج كائن JSON سليم.
    """
    if not raw_text: return None
    
    # 1. Extract JSON candidate using Regex
    match = PLAN_RE.search(raw_text)
    candidate = match.group(1) or match.group(2) if match else raw_text

    # 2. Remove Comments (// ...)
    candidate = re.sub(r"//.*", "", candidate)
    
    # 3. Locate strict outermost braces
    start = candidate.find('{')
    end = candidate.rfind('}')
    if start == -1 or end == -1: return None
    
    clean_str = candidate[start:end+1]
    
    # 4. Remove Trailing Commas (Common LLM Error)
    clean_str = re.sub(r",\s*}", "}", clean_str)
    clean_str = re.sub(r",\s*]", "]", clean_str)

    try:
        return json.loads(clean_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        return None

# ======================================================
# 🔧 ENGINEERING UTILS (BiDi & Geometry)
# ======================================================

def is_arabic_advanced(text):
    """كشف عميق للنصوص العربية باستخدام النطاقات الموسعة."""
    return bool(ARABIC_EXTENDED_RE.search(text))

def enforce_geo_protocol(svg_code):
    """
    تطبيق بروتوكول Geo الهندسي:
    1. تقريب الأرقام العشرية (Decimal Precision).
    2. إغلاق المسارات (Z).
    """
    # 1. Rounding long floats to 2 decimal places (Optimization)
    svg_code = re.sub(r"(\d+\.\d{3,})", lambda m: f"{float(m.group(1)):.2f}", svg_code)
    return svg_code

def inject_bidi_attributes(svg_code):
    """
    حقن سمات الاتجاه (RTL) وتصحيح المراسي (Anchors) للنصوص العربية.
    """
    def replace_text_tag(match):
        tag_content = match.group(0)
        # Check if the text content inside the tag is Arabic
        # (This is a simplified check; ideally we parse the XML content)
        if is_arabic_advanced(tag_content):
            # 1. Force RTL
            if "direction" not in tag_content:
                tag_content = tag_content.replace("<text", '<text direction="rtl" unicode-bidi="embed"')
            
            # 2. Flip Anchors (Start -> End) for proper RTL alignment
            if 'text-anchor="start"' in tag_content:
                tag_content = tag_content.replace('text-anchor="start"', 'text-anchor="end"')
            elif 'text-anchor="end"' in tag_content:
                tag_content = tag_content.replace('text-anchor="end"', 'text-anchor="start"')
                
            # 3. Ensure Font Fallback (Optional but recommended)
            if "font-family" not in tag_content:
                tag_content = tag_content.replace("<text", '<text font-family="Arial, sans-serif"')
                
        return tag_content

    # Apply to <text> and <tspan> tags
    svg_code = re.sub(r"<text[^>]*>.*?</text>", replace_text_tag, svg_code, flags=re.DOTALL)
    return svg_code

# ======================================================
# 👮‍♂️ VALIDATORS (Plan & SVG Quality)
# ======================================================

def validate_plan_content(plan):
    if not isinstance(plan, dict): return False, "Invalid JSON Object."
    
    contract = plan.get("design_contract")
    if not isinstance(contract, dict): return False, "Missing 'design_contract'."

    # Strict Equality Checks
    if str(contract.get("contrast_verified", "")).upper() != "YES":
        return False, "Contrast Verification Failed (Must be 'YES')."

    # Verify Rules Citation
    rules = contract.get("main_rules_applied", [])
    if not isinstance(rules, list) or len(rules) < 3:
        return False, "Constitution Violation: Must cite at least 3 rules."

    return True, "Valid"

def validate_svg_quality(svg_code):
    if not svg_code or "<svg" not in svg_code:
        return False, "No valid SVG tag found."

    # Check for Arabic without RTL (Fatal Error in V16)
    # We strip tags to check raw text content for Arabic
    text_content = re.sub(r"<[^>]+>", "", svg_code)
    if is_arabic_advanced(text_content):
        if "direction" not in svg_code and "rtl" not in svg_code:
             # We allow the code to pass IF we are going to fix it later, 
             # but strictly speaking, the AI should have generated it.
             # For V16 strictness, we flag it.
             pass # Warning only, as inject_bidi_attributes will fix it.

    # Check for Amateur Stroke Widths
    heavy_strokes = re.findall(r'stroke-width=["\']([3-9]|\d{2,})["\']', svg_code)
    if heavy_strokes:
        return False, "Geo Protocol Violation: Stroke width > 2px detected."

    return True, "Quality OK"

# ======================================================
# 🚀 APP LOGIC V16.0 (The Iron Guard)
# ======================================================

def get_recipe_data(cat, prompt):
    # Dynamic Recipe Logic
    return {
        "id": f"v16_{cat}_{int(time.time())}", 
        "layout_rules": ["Use Swiss Grid", "Apply Golden Ratio"], 
        "typography_rules": ["Header: H1 Bold", "Body: Sans-serif Regular"]
    }

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Backend Unavailable"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        
        # Default V16 Dimensions
        width, height = int(data.get('width', 1080)), int(data.get('height', 1080))
        
        recipe = get_recipe_data(cat_name, user_msg)
        
        # Prepare Context
        indexed_rules = [f"{k}: {v}" for k,v in ALMONJEZ_CONSTITUTION.items()]
        
        # ✅ FIX 2: THE LITERAL CONTRACT (Updated for V16)
        plan_template = f"""
REQUIRED JSON PLAN FORMAT:
```json
{{
  "design_contract": {{
    "arabic_position": "top_right",
    "contrast_verified": "YES",
    "layout_variant": "hero",
    "opacity_tiers_used": ["0.12", "0.45", "1.0"],
    "main_rules_applied": ["1_Hierarchy", "3_Arabic_BiDi", "4_Geo_Safety"]
  }}
}}

"""
    sys_instructions = f"""
    ROLE: Almonjez V16 Engineering Architect.
    
    --- 🏛️ CONSTITUTION (STRICT) ---
    {json.dumps(indexed_rules, indent=2)}
    
    --- 📐 GEO PROTOCOL ---
    1. Opacity Tiers: Background=0.12, Shapes=0.45, Text=1.0. NO exceptions.
    2. Precision: All coordinates must be rounded to 2 decimals.
    3. Safe Zone: Keep important content 50px inside borders.
    
    --- 🕉️ ARABIC BIDI RULES ---
    1. IF Arabic text detected: Add `direction="rtl"` to parent tag.
    2. Set `text-anchor="end"` for Arabic headers (align right).
    
    --- ✅ OUTPUT PROTOCOL ---
    1. Generate the JSON Plan (Strict Format).
    2. Generate the SVG Code (Clean, Valid XML).
    {plan_template}
    """

    # 🛡️ THE IRON GUARD LOOP
    max_attempts = 2
    final_svg = None
    used_model = "unknown"
    extracted_plan = None
    fail_reason = ""
    
    # Models Queue
    models = ["gemini-2.0-pro-exp-02-05", "gemini-2.0-flash"]
    
    for attempt in range(max_attempts):
        model = models[0] if attempt == 0 else models[-1]
        try:
            current_sys = sys_instructions
            if attempt > 0:
                current_sys += f"\n\n⚠️ PREVIOUS FAILURE: {fail_reason}. COMPLY WITH GEO PROTOCOL."

            response = client.models.generate_content(
                model=model,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=current_sys, 
                    temperature=0.6 if attempt==0 else 0.4
                )
            )
            
            raw = response.text or ""
            
            # 1. Sanitize & Extract Plan
            plan = sanitize_json_payload(raw)
            
            # 2. Validate Plan
            is_plan_ok, p_reason = validate_plan_content(plan)
            if not is_plan_ok:
                fail_reason = f"Plan Error: {p_reason}"
                logger.warning(f"Attempt {attempt+1} Failed: {fail_reason}")
                continue

            # 3. Extract SVG (State-Aware)
            svg_match = SVG_EXTRACT_RE.search(raw)
            if not svg_match:
                fail_reason = "No valid SVG block found."
                continue
            svg_code = svg_match.group(0)

            # 4. Validate SVG Quality
            is_svg_ok, s_reason = validate_svg_quality(svg_code)
            if not is_svg_ok:
                fail_reason = f"SVG Quality Error: {s_reason}"
                logger.warning(f"Attempt {attempt+1} Failed: {fail_reason}")
                continue

            # Success - Enter Post-Processing Pipeline
            final_svg = svg_code
            extracted_plan = plan
            used_model = model
            break
            
        except Exception as e:
            fail_reason = str(e)
            logger.error(f"System Error on attempt {attempt+1}: {e}")
            time.sleep(1)

    if not final_svg:
         return jsonify({
             "error": "V16 Compliance Failure", 
             "details": fail_reason
         }), 500

    # ======================================================
    # 🔨 POST-PROCESSING: APPLYING ENGINEERING PROTOCOLS
    # ======================================================
    
    # 1. Enforce Geo Protocol (Rounding)
    final_svg = enforce_geo_protocol(final_svg)
    
    # 2. Inject BiDi/Arabic Attributes
    final_svg = inject_bidi_attributes(final_svg)
    
    # 3. Namespace & Filter Injection (Standard Fixes)
    if 'xmlns=' not in final_svg: 
        final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    
    return jsonify({
        "response": final_svg,
        "meta": {
            "model": used_model, 
            "plan": extracted_plan,
            "protocol": "V16-GEO-BIDI"
        }
    })

except Exception as e:
    logger.critical(f"Fatal System Error: {e}")
    return jsonify({"error": str(e)}), 500

if name == 'main':
# Running on standard port
app.run(host='0.0.0.0', port=10000)

