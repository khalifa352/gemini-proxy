import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ======================================================
# 🔌 AI CLIENT SETUP (Robust Import)
# ======================================================
client = None
try:
    # المكتبة الجديدة (v1.0+)
    from google import genai
    from google.genai import types
    
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        logger.info("✅ Google GenAI Client Connected Successfully.")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY not found in environment variables.")

except ImportError:
    logger.error("❌ Library Error: 'google-genai' not installed. Run: pip install google-genai")
except Exception as e:
    logger.error(f"❌ AI Client Error: {e}")

# ======================================================
# 🛡️ V16 RECOGNITION & EXTRACTION
# ======================================================

# تحسين Regex لالتقاط JSON بمرونة أكبر
PLAN_RE = re.compile(r"(?:Plan|JSON|RESPONSE):\s*(.*?)(?=\n\n|SVG:|Code:|```|$)", re.DOTALL | re.IGNORECASE)
ARABIC_RANGE_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
SVG_EXTRACT_RE = re.compile(r"(?s)<svg[^>]*>.*?</svg>")

# ======================================================
# 🏛️ ALMONJEZ CONSTITUTION
# ======================================================
ALMONJEZ_CONSTITUTION = {
    "1_Hierarchy": "Headlines MUST be 3x body size. No floating elements.",
    "2_Contrast": "Dark text on Light BG only. Light text on Dark BG only. Use backing rects if needed.",
    "3_Arabic": "Arabic Title = Top/Right & Largest. English = Secondary.",
    "4_EmptySpace": "Fill dead space with: Pattern (5% opacity) or Service Pills.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required."
}

# ======================================================
# 👮‍♂️ GEO PROTOCOL VALIDATORS
# ======================================================

def extract_plan(raw_text):
    match = PLAN_RE.search(raw_text or "")
    content = match.group(1).strip() if match else ""
    # تنظيف Markdown
    content = re.sub(r'^```json\s*|```$', '', content, flags=re.MULTILINE)
    try:
        return json.loads(content)
    except:
        # محاولة التقاط أي كائن JSON
        bracket_match = re.search(r'(\{.*\})', raw_text or "", re.DOTALL)
        if bracket_match:
            try: return json.loads(bracket_match.group(1))
            except: return None
    return None

def validate_plan_content(plan):
    if not isinstance(plan, dict): return False, "Missing JSON Plan."
    contract = plan.get("design_contract")
    if not isinstance(contract, dict): return False, "Missing 'design_contract'."

    if str(contract.get("arabic_position", "")).lower() != "top_right":
        return False, "Arabic Position MUST be 'top_right'."
    
    # تحقق مخفف لتجنب الرفض الزائف
    if str(contract.get("contrast_verified", "")).upper() not in ["YES", "TRUE"]:
        return False, "Contrast verification failed."

    return True, "Valid"

def validate_svg_quality(svg_code):
    if not svg_code or "<svg" not in svg_code:
        return False, "Invalid SVG code."

    # 1. BiDi Check
    if ARABIC_RANGE_RE.search(svg_code):
        if "direction: rtl" not in svg_code.lower() and "direction:rtl" not in svg_code.lower():
            # نسمح بالمرور إذا كانت هناك محاولة style ولكن نفضل التحذير
            if "style" not in svg_code:
                return False, "Geo Error: Arabic detected without styling."

    # 2. Precision Check (Geo Protocol)
    if re.search(r'\d+\.\d{5,}', svg_code): # السماح حتى 4 منازل، رفض 5 فما فوق
        return False, "Geo Error: Precision bloat (>4 decimals)."

    return True, "Quality OK"

# ======================================================
# 📐 GEOMETRY KITS
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
    return {"assets": {"curve_XL": get_path(60), "curve_L": get_path(30), "curve_M": get_path(0)}}

def supply_sharp_kit(width, height, seed):
    rnd = random.Random(seed)
    w, h = int(width), int(height)
    peak = int(h * 0.25)
    p_y = h - peak
    path_back = f"M0,{h} L0,{p_y} L{w/2},{p_y-50} L{w},{p_y} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_y+40} L{w/2},{p_y+20} L{w},{p_y+40} L{w},{h} Z"
    return {"assets": {"poly_back": path_back, "poly_front": path_front}}

def analyze_needs(user_msg):
    msg = str(user_msg).lower()
    if 'curve' in msg or 'soft' in msg: return 'CURVE'
    if 'sharp' in msg or 'tech' in msg: return 'SHARP'
    return 'NONE'

# ======================================================
# 🚀 APP LOGIC
# ======================================================

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: 
        return jsonify({"error": "AI Client not initialized. Check logs/API Key."}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        geo_mode = analyze_needs(user_msg)
        seed = random.randint(0, 999999)
        
        # Geometry Logic
        geo_kit = supply_curve_kit(width, height, seed) if geo_mode == 'CURVE' else supply_sharp_kit(width, height, seed) if geo_mode == 'SHARP' else None
        geo_instr = f"ASSETS: {json.dumps(geo_kit['assets'])}" if geo_kit else "Focus on Typography & Layout."

        plan_template = """
        Your response MUST follow the Geo Protocol V16:
        1. JSON Plan inside ```json blocks.
        2. SVG: direction:rtl for Arabic.
        3. SVG: All shapes closed with 'Z'.
        {
          "design_contract": {
            "arabic_position": "top_right",
            "contrast_verified": "YES",
            "layout_variant": "hero",
            "main_rules_applied": ["1_Hierarchy", "2_Contrast", "3_Arabic"]
          }
        }
        """

        sys_instructions = f"""
        ROLE: Almonjez Art Director V16.
        --- 🏛️ CONSTITUTION ---
        {json.dumps(ALMONJEZ_CONSTITUTION, ensure_ascii=False)}
        {geo_instr}
        --- ✅ OUTPUT RULE ---
        1. FIRST: The Plan JSON block.
        2. THEN: The SVG code.
        {plan_template}
        """

        # ✅ قائمة الموديلات المحدثة (Gemini 2.0 Flash First)
        # نضع Flash أولاً للسرعة، ثم Pro 2.0 التجريبي للجودة، ثم 1.5 Pro للاستقرار
        models = [
            "gemini-2.0-flash",           # الأسرع والأحدث
            "gemini-2.0-pro-exp-02-05",   # الأقوى (تجريبي)
            "gemini-1.5-pro"              # المستقر
        ]
        
        max_attempts = 2
        final_svg, used_model, extracted_plan, fail_reason = None, "unknown", None, ""

        for attempt in range(max_attempts):
            # محاولة استخدام الموديل الأول، ثم الموديل الاحتياطي
            model = models[0] if attempt == 0 else models[1] 
            
            try:
                # تكوين الطلب
                config = types.GenerateContentConfig(
                    system_instruction=sys_instructions,
                    temperature=0.7 if attempt == 0 else 0.4
                )
                
                # إضافة تلميح للإصلاح في المحاولة الثانية
                prompt_content = user_msg
                if attempt > 0:
                    prompt_content += f"\n\n⚠️ PREVIOUS ERROR: {fail_reason}. Please fix format."

                response = client.models.generate_content(
                    model=model,
                    contents=prompt_content,
                    config=config
                )
                
                raw = response.text or ""
                plan = extract_plan(raw)
                
                # Validation Loop
                is_plan_ok, p_reason = validate_plan_content(plan)
                if not is_plan_ok:
                    fail_reason = f"Plan Error: {p_reason}"
                    continue

                svg_matches = SVG_EXTRACT_RE.findall(raw)
                svg_code = svg_matches[0] if svg_matches else ""
                
                is_svg_ok, s_reason = validate_svg_quality(svg_code)
                if not is_svg_ok:
                    fail_reason = f"Geo Quality: {s_reason}"
                    continue

                final_svg, extracted_plan, used_model = svg_code, plan, model
                break

            except Exception as e:
                fail_reason = str(e)
                logger.error(f"Attempt {attempt} failed with {model}: {e}")
                time.sleep(1)

        if not final_svg:
             return jsonify({"error": f"Failed Geo-Audit: {fail_reason}"}), 500

        # Post-processing
        if 'xmlns=' not in final_svg: 
            final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        return jsonify({
            "response": final_svg,
            "meta": {"model": used_model, "plan": extracted_plan}
        })

    except Exception as e:
        logger.error(f"Server Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
