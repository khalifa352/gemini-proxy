import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ CONFIGURATION
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_V17_Modular")

app = Flask(__name__)

# ======================================================
# 🔌 AI CLIENT (PAID TIER - PRO MODELS)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        # Paid Tier: Access to 1.5 Pro (The Best Designer)
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Almonjez Architect Connected (Paid Tier).")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY Missing.")
except Exception as e:
    logger.error(f"❌ Client Init Error: {e}")

# ======================================================
# 📐 THE "FREEPIK" ENGINE (PYTHON GEOMETRY)
# ======================================================
# هذه الوظيفة هي بديل "فري بيك". إذا طلبت الوصفة كيرفات، 
# تقوم بايثون بحسابها رياضياً لضمان النعومة وعدم التشوه.

def generate_geometry_assets(width, height, engine_type):
    w, h = int(width), int(height)
    assets = {}
    
    # 1. محرك الكيرفات العضوي (للوصفات الطبية/الناعمة)
    if engine_type == "organic_curves":
        # كيرف علوي انسيابي (Header)
        assets['path_header'] = f"M0,0 L{w},0 L{w},{h*0.35} C{w*0.75},{h*0.25} {w*0.25},{h*0.55} 0,{h*0.45} Z"
        # كيرف سفلي (Footer)
        assets['path_footer'] = f"M0,{h} L{w},{h} L{w},{h*0.85} C{w*0.6},{h*0.75} {w*0.4},{h*0.95} 0,{h*0.85} Z"
        # دائرة زخرفية (Accent)
        assets['shape_accent'] = f"M{w*0.85},{h*0.15} m-50,0 a50,50 0 1,0 100,0 a50,50 0 1,0 -100,0"

    # 2. محرك المضلعات الحادة (للتقنية/الشركات)
    elif engine_type == "sharp_polygons":
        # قطع قطري حاد (Diagonal Slice)
        assets['path_header'] = f"M0,0 L{w},0 L{w},{h*0.2} L0,{h*0.35} Z"
        # مثلث زخرفي
        assets['path_footer'] = f"M{w},{h} L{0},{h} L{w},{h*0.8} Z"
        # شبكة (Grid Pattern)
        assets['shape_accent'] = f"M{w*0.9},{h*0.1} L{w*0.95},{h*0.15} L{w*0.9},{h*0.2}"

    # 3. محرك الشبكة السويسرية (للتصاميم الرسمية)
    elif engine_type == "swiss_grid":
        # خطوط تقسيم فقط (Dividers)
        assets['line_divider_1'] = f"M{w*0.05},{h*0.3} L{w*0.95},{h*0.3}"
        assets['line_divider_2'] = f"M{w*0.05},{h*0.7} L{w*0.95},{h*0.7}"
        # مربع نص
        assets['rect_frame'] = f"M{w*0.05},{h*0.05} L{w*0.95},{h*0.05} L{w*0.95},{h*0.95} L{w*0.05},{h*0.95} Z"

    # إذا كانت الوصفة تقول "none" أو غير معروفة، نترك جيميني يرسم
    else:
        return None 

    return assets

# ======================================================
# 🚀 MAIN LOGIC (THE EXECUTIONER)
# ======================================================
@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 800))
        height = int(data.get('height', 600))
        
        # 1. استلام الوصفة من الخارج (العميل يرسلها)
        # The frontend/app sends the full recipe object here
        recipe = data.get('recipe', {}) 
        
        # التحقق من وجود وصفة، وإلا استخدام وصفة افتراضية
        if not recipe:
            logger.warning("No recipe provided, using fallback.")
            recipe = {"id": "GENERIC", "geometry_engine": "none", "layout_rules": ["Standard Layout"]}

        # 2. تشغيل "محرك فري بيك" (Python Geometry)
        # نتحقق مما إذا كانت الوصفة تطلب تدخلاً هندسياً من الكود
        engine_type = recipe.get('geometry_engine', 'none')
        geo_assets = generate_geometry_assets(width, height, engine_type)
        
        # تجهيز تعليمات الأصول
        assets_instruction = ""
        if geo_assets:
            assets_instruction = f"""
            === 🧱 GEOMETRY ASSETS (PROVIDED BY ENGINE) ===
            You MUST use these exact path data strings. Do not redraw the main shapes.
            Apply the colors from the palette to these paths.
            {json.dumps(geo_assets, indent=2)}
            """
        else:
            assets_instruction = "=== 🧱 GEOMETRY ===\nDraw the shapes yourself based on the recipe description."

        # 3. بناء "أمر العمل" (The Design Brief)
        system_instruction = f"""
        ROLE: Senior Art Director (Almonjez V17).
        TASK: Execute the provided Design Recipe exactly.

        === 📜 RECIPE CARD: {recipe.get('id', 'Custom')} ===
        Description: {recipe.get('description', '')}
        Mood: {recipe.get('mood', 'Professional')}
        
        === 📐 LAYOUT RULES (STRICT) ===
        {json.dumps(recipe.get('layout_rules', []), indent=2)}
        
        === 🔤 TYPOGRAPHY RULES ===
        {json.dumps(recipe.get('typography_rules', []), indent=2)}

        {assets_instruction}

        === 🎨 COLOR STRATEGY ===
        Follow the 'generative_rules' in the recipe if available. 
        Ensure high contrast.

        === 🌍 ARABIC SUPPORT (NON-NEGOTIABLE) ===
        - All Arabic text groups MUST have `direction="rtl"`.
        - Use `text-anchor="end"` for Arabic text.
        - Font-family fallback: "Arial, sans-serif".

        === ✅ OUTPUT ===
        1. JSON Plan (Confirming recipe compliance).
        2. SVG Code (Clean, Minified).
        """

        # 4. اختيار الموديل (أنت تدفع، إذن نستخدم الأقوى)
        # 1.5 Pro: الأفضل في فهم التعليمات المعقدة والالتزام بالوصفات
        model_name = "gemini-1.5-pro" 
        
        response = client.models.generate_content(
            model=model_name,
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4 # توازن مثالي بين الالتزام والإبداع
            )
        )
        
        raw_text = response.text or ""
        
        # 5. استخراج SVG
        # نستخدم Regex قوي لضمان التقاط الكود
        svg_match = re.search(r"(?s)<svg[^>]*>.*?</svg>", raw_text)
        if not svg_match:
            return jsonify({"error": "Failed to generate SVG"}), 500
            
        final_svg = svg_match.group(0)
        
        # إضافة Namespace إذا نسيه الموديل
        if 'xmlns=' not in final_svg:
            final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        # استخراج الخطة للعرض (اختياري)
        plan_match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
        plan = json.loads(plan_match.group(1)) if plan_match else {}

        return jsonify({
            "response": final_svg,
            "meta": {
                "model": model_name,
                "recipe_id": recipe.get('id'),
                "engine_used": engine_type,
                "plan": plan
            }
        })

    except Exception as e:
        logger.error(f"System Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
