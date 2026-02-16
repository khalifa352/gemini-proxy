import os
import json
import logging
from flask import Flask, request, jsonify

# إعداد السجلات لنرى سبب التوقف إن وجد
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- محاولة الاتصال بـ Google GenAI ---
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        logger.info("✅ GenAI Client Connected Successfully")
    else:
        logger.warning("⚠️ Warning: GOOGLE_API_KEY not found")
except Exception as e:
    logger.error(f"❌ GenAI Import Error: {e}")

# --- محرك الطبقات والمنحنيات (Layered Waves Engine) ---
def generate_layered_waves(width, height):
    """
    يولد 3 طبقات منحنية متداخلة (خلفية، وسطى، أمامية).
    """
    # تحويل الأبعاد لأرقام صحيحة لتجنب الكسور
    w = int(width)
    h = int(height)
    
    # ارتفاع الموجة
    amp = int(h * 0.25) 
    
    # نقاط التحكم (Control Points)
    p_start_y = h - int(amp * 0.8)
    p_end_y = h - int(amp * 0.4)
    
    cp1_x = int(w * 0.3)
    cp1_y = h - int(amp * 1.5)
    
    cp2_x = int(w * 0.7)
    cp2_y = h - int(amp * 0.1)

    # توليد المسارات (Paths)
    # الطبقة الخلفية (الأوسع)
    path_back = f"M0,{h} L0,{p_start_y} C{cp1_x},{cp1_y-40} {cp2_x},{cp2_y+40} {w},{p_end_y} L{w},{h} Z"
    
    # الطبقة الوسطى
    path_mid = f"M0,{h} L0,{p_start_y+20} C{cp1_x+20},{cp1_y} {cp2_x-20},{cp2_y+20} {w},{p_end_y+20} L{w},{h} Z"
    
    # الطبقة الأمامية (الأضيق)
    path_front = f"M0,{h} L0,{p_start_y+50} C{cp1_x+50},{cp1_y+40} {cp2_x-50},{cp2_y+50} {w},{p_end_y+50} L{w},{h} Z"
    
    # حساب المنطقة الآمنة (أعلى نقطة تصل إليها الموجات)
    # نأخذ أقل قيمة Y (لأن الصفر في الأعلى) ونطرح هامشاً
    min_y = min(p_start_y, p_end_y, cp1_y, cp2_y)
    safe_bottom = min_y - 50
    
    return {
        "back": path_back,
        "mid": path_mid,
        "front": path_front
    }, safe_bottom

# --- المسار الرئيسي (فحص الصحة) ---
@app.route('/')
def home():
    return "Almonjez Pro Engine is Running! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client:
        return jsonify({"error": "Server Error: AI Client not initialized"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        # الأبعاد الافتراضية
        width = int(data.get('width', 800))
        height = int(data.get('height', 600))
        
        # 1. حساب الطبقات رياضياً
        layers, safe_bottom_y = generate_layered_waves(width, height)
        
        # تحديد منطقة النص الآمنة
        text_zone_top = 50
        text_zone_height = safe_bottom_y - text_zone_top

        # 2. التعليمات
        sys_instructions = f"""
        Role: Senior Vector Designer.
        Task: Create a multi-layer SVG with perfect geometry and contrast.
        
        --- 🎨 GEOMETRY INSTRUCTIONS (USE THESE PATHS) ---
        I have pre-calculated 3 interlocking wave paths for the footer. You MUST use them:
        1. **Layer 1 (Back)**: Path="{layers['back']}" (Opacity 0.2)
        2. **Layer 2 (Mid)**:  Path="{layers['mid']}"  (Opacity 0.6)
        3. **Layer 3 (Front)**: Path="{layers['front']}" (Opacity 1.0 - Darkest)
        
        --- 📐 LAYOUT & SAFETY (STRICT) ---
        1. **Text Safe Zone**: 
           - ALL text must be inside the upper white space (Y=0 to Y={safe_bottom_y}).
           - NO text is allowed to overlap the footer waves.
        
        2. **Typography**:
           - Use <foreignObject> for all text.
           - Text Container Height: {text_zone_height}px.
           - Alignment: Center or Justify.
        
        3. **Contrast Protocol**:
           - Background White -> Text Black (#111111).
           - Footer Dark -> Footer Text White (#FFFFFF).
        
        INPUT:
        - Content: "{user_msg}"
        - ViewBox: 0 0 {width} {height}
        
        OUTPUT:
        - Return ONLY raw SVG code.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=0.7)
        )

        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        # إصلاح مشاكل العرض في آيفون
        if '<svg' in svg_output and 'xmlns=' not in svg_output:
            svg_output = svg_output.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
            
        return jsonify({"response": svg_output})

    except Exception as e:
        logger.error(f"Runtime Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
