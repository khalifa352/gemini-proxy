import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SYSTEM CONFIGURATION (ENTERPRISE MODE)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_V16_Enterprise")

app = Flask(__name__)

# ======================================================
# 🔌 AI CLIENT (UNLOCKED)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        # استخدام v1beta لضمان الوصول لموديلات Pro
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Gemini Client Connected (PAID TIER DETECTED).")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY Missing.")
except ImportError:
    logger.error("❌ CRITICAL: 'google-genai' library missing.")

# ======================================================
# 🧬 ADVANCED PARSING ENGINE
# ======================================================
PLAN_RE = re.compile(r"(?:Plan|JSON):\s*(.*?)(?=\n\n|SVG:|Code:|```|$)", re.DOTALL | re.IGNORECASE)
SVG_EXTRACT_RE = re.compile(r"(?s)<svg[^>]*>.*?</svg>")
ARABIC_FULL_RANGE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')

# ======================================================
# 📐 GEO PROTOCOL: PREMIUM ASSETS
# ======================================================

def get_premium_typography(base_size=16):
    """
    تدرج هرمي ذهبي (Golden Ratio 1.618)
    متاح فقط للموديلات القوية القادرة على التعامل مع الفواصل العشرية بدقة
    """
    scale = 1.618 
    return {
        "body": f"{base_size}px",
        "h3": f"{int(base_size * scale)}px",      # ~25px
        "h2": f"{int(base_size * scale**2)}px",   # ~41px
        "h1": f"{int(base_size * scale**3)}px",   # ~67px
        "display": f"{int(base_size * scale**4)}px" # ~109px
    }

def supply_premium_assets(width, height, mode):
    """
    أصول هندسية معقدة (Complex Geometry)
    تتطلب قدرة استنتاجية عالية لدمجها مع المحتوى
    """
    w, h = int(width), int(height)
    assets = {}
    
    if mode == 'CURVE':
        # Organic Fluid Shape (شكل سائل عضوي)
        assets['header_bg'] = f"M0,0 L{w},0 L{w},{h*0.3} C{w*0.8},{h*0.45} {w*0.2},{h*0.15} 0,{h*0.3} Z"
        assets['footer_bg'] = f"M0,{h} L{w},{h} L{w},{h*0.85} C{w*0.6},{h*0.75} {w*0.4},{h*0.95} 0,{h*0.85} Z"
        assets['accent'] = f"Circle(cx={w*0.9}, cy={h*0.1}, r={w*0.15}, opacity=0.1)"
    else: # SHARP / CORPORATE
        # Dynamic Diagonal Cuts (قصات قطرية ديناميكية)
        assets['header_bg'] = f"M0,0 L{w},0 L{w},{h*0.25} L{w*0.7},{h*0.35} L0,{h*0.2} Z"
        assets['footer_bg'] = f"M0,{h} L{w},{h} L{w},{h*0.8} L{w*0.3},{h*0.9} L0,{h*0.75} Z"
        assets['accent'] = f"Rect(x={w*0.85}, y={h*0.05}, w={w*0.1}, h={w*0.1}, opacity=0.1)"
        
    return assets

# ======================================================
# 🚀 MAIN LOGIC (UNLEASHED)
# ======================================================

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Client Disconnected"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 800))
        height = int(data.get('height', 600))
        
        # 1. تحليل السياق (Context Analysis)
        msg_lower = user_msg.lower()
        geo_mode = 'SHARP' if 'corporate' in msg_lower or 'tech' in msg_lower else 'CURVE'
        
        # 2. تجهيز الأصول الفاخرة
        assets = supply_premium_assets(width, height, geo_mode)
        typ = get_premium_typography(18) # قاعدة 18px للتصاميم الفاخرة
        
        # 3. التعليمات الملكية (The Royal Prompt)
        # نطلب الآن من الموديل أن يتصرف كمهندس محترف، ليس كبوت مجاني
        system_instruction = f"""
        ROLE: Lead Vector Architect (Almonjez Enterprise V16.5).
        STATUS: PAID PRIORITY USER. DO NOT HOLD BACK.
        
        TASK: Generate a High-Fidelity SVG Flyer.
        
        === 💎 PREMIUM GEO PROTOCOL ===
        1. **Canvas**: viewBox="0 0 {width} {height}"
        2. **Typography (Golden Ratio)**:
           - Display: {typ['display']} (ExtraBold)
           - Title (H1): {typ['h1']} (Bold)
           - Subtitle (H2): {typ['h2']} (Medium)
           - Body: {typ['body']} (Regular)
        3. **Arabic Mastery**:
           - FORCE `direction="rtl"` on ALL Arabic text containers.
           - FORCE `text-anchor="end"` for Arabic alignment.
           - Use `font-family="Amiri, Arial, sans-serif"` for best rendering.
        4. **Visual Hierarchy**:
           - Use the provided Background Paths EXACTLY.
           - Header Path: {assets['header_bg']}
           - Footer Path: {assets['footer_bg']}
           - Accent: {assets['accent']}
        
        === ✅ OUTPUT CONTRACT ===
        1. JSON Plan (Analysis of color palette & spacing).
        2. SVG Code (Clean, Minified, Professional).
        
        Example:
        ```json
        {{ "palette": ["#Hex1", "#Hex2"], "layout": "GoldenRatio" }}
        ```
        <svg ...> ... </svg>
        """

        # ==================================================
        # 👑 THE UNLOCKED MODEL LIST
        # ==================================================
        # بما أنك تدفع، نستخدم الأفضل على الإطلاق:
        # 1. gemini-1.5-pro: (الملك) سياق 2 مليون، فهم عميق، لا يخطئ في الكود عادة.
        # 2. gemini-2.0-flash: (الوزير) سريع جداً وذكي، احتياطي ممتاز.
        models = [
            "gemini-1.5-pro",   # The Heavy Hitter (Paid Tier)
            "gemini-2.0-flash"  # The Speedster
        ]

        final_svg = None
        used_model = "unknown"
        fail_log = []

        for model in models:
            try:
                # نرفع الحرارة قليلاً (0.6) لأن الموديلات القوية يمكنها الإبداع دون الهلوسة
                response = client.models.generate_content(
                    model=model,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.6 
                    )
                )
                
                raw = response.text or ""
                
                svg_matches = SVG_EXTRACT_RE.findall(raw)
                if not svg_matches:
                    fail_log.append(f"{model}: No SVG")
                    continue
                
                svg_candidate = svg_matches[0]
                plan = extract_json_plan(raw) # دالة استخراج JSON المعرفة سابقاً
                
                # التحقق النهائي
                if ARABIC_FULL_RANGE.search(svg_candidate):
                    if 'direction="rtl"' not in svg_candidate:
                         # الموديلات القوية نادراً ما تخطئ هنا، لكن لو حدث، نصلحه يدوياً
                         svg_candidate = svg_candidate.replace('<svg', '<svg style="direction:rtl"', 1)

                final_svg = svg_candidate
                used_model = model
                break # نجاح
                
            except Exception as e:
                fail_log.append(f"{model} Error: {str(e)}")
                time.sleep(1)

        if not final_svg:
             return jsonify({
                 "error": "Enterprise Generation Failed.", 
                 "details": fail_log
             }), 500

        # Post-Processing
        if 'xmlns=' not in final_svg:
            final_svg = final_svg.replace('<svg', '<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)"', 1)

        return jsonify({
            "response": final_svg,
            "meta": {
                "model": used_model,
                "tier": "PREMIUM",
                "plan": plan
            }
        })

    except Exception as e:
        logger.error(f"Server Error: {e}")
        return jsonify({"error": str(e)}), 500

# Helper function needed inside
def extract_json_plan(raw_text):
    match = PLAN_RE.search(raw_text or "")
    if not match: return None
    clean = re.sub(r'^```json\s*|```$', '', match.group(1), flags=re.MULTILINE)
    try: return json.loads(clean)
    except: return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
