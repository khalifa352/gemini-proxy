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

# --- 🧠 محرك الطبقات المتداخلة (The Multi-Layer Mesh Engine) ---
def generate_layered_waves(width, height, position='bottom'):
    """
    يولد 'عائلة' من المنحنيات المترابطة (ليست عشوائية).
    تخرج من نفس الأطراف وتتوسع في المنتصف لتعطي تأثير 'الخروج من تحت'.
    """
    assets = {}
    
    # إعدادات الموجة الرئيسية
    if position == 'bottom':
        # أقصى ارتفاع للموجة (مثلاً 25% من الشاشة)
        amplitude = height * 0.25
        base_y = height  # تبدأ من الأسفل
        
        # نقاط التحكم الأساسية (Master Control Points)
        # موجة تبدأ عالية من اليسار وتنخفض لليمين (أو العكس)
        p0 = (0, height - (amplitude * 0.8))  # اليسار
        p3 = (width, height - (amplitude * 0.4)) # اليمين
        
        # نقاط التحكم في المنتصف (لعمل الـ S-Curve)
        cp1 = (width * 0.3, height - amplitude * 1.5)
        cp2 = (width * 0.7, height - amplitude * 0.1)
        
        # --- الطبقة 1: الخلفية الباهتة (أكبر وأوسع) ---
        path1 = f"M0,{height} L{p0[0]},{p0[1]} C{cp1[0]},{cp1[1]-40} {cp2[0]},{cp2[1]+40} {p3[0]},{p3[1]} L{width},{height} Z"
        assets['layer_back'] = path1
        
        # --- الطبقة 2: الطبقة الوسطى (لون مختلف) ---
        # نغير نقاط التحكم قليلاً لنخلق "فراغاً" بين الطبقات
        path2 = f"M0,{height} L{p0[0]},{p0[1]+20} C{cp1[0]+20},{cp1[1]} {cp2[0]-20},{cp2[1]+20} {p3[0]},{p3[1]+20} L{width},{height} Z"
        assets['layer_mid'] = path2
        
        # --- الطبقة 3: الموجة الرئيسية (الأمامية الداكنة) ---
        path3 = f"M0,{height} L{p0[0]},{p0[1]+50} C{cp1[0]+50},{cp1[1]+40} {cp2[0]-50},{cp2[1]+50} {p3[0]},{p3[1]+50} L{width},{height} Z"
        assets['layer_front'] = path3
        
        # حساب المنطقة الآمنة للنص (فوق أعلى نقطة في الموجات)
        safe_bottom_limit = min(p0[1], p3[1], cp1[1], cp2[1]) - 50
        
        return assets, safe_bottom_limit

    return {}, height

@app.route('/')
def home(): return "Almonjez Pro: Layered Curves & Grid Layout Active 📐"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Client Error"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        # 1. توليد الطبقات الرياضية
        # سنولد مجموعة للسفل ومجموعة للأعلى
        bottom_layers, safe_y_bottom = generate_layered_waves(width, height, 'bottom')
        
        # 2. حساب منطقة النص (The Strict Text Box)
        # النص يجب أن يكون محصوراً تماماً في المساحة البيضاء
        text_zone_height = safe_y_bottom - 100 # هامش علوي 100 بكسل
        text_zone_y_start = 50 
        
        # 3. التعليمات الصارمة
        sys_instructions = f"""
        Role: Senior Vector Artist & Typography Expert.
        Task: Assemble a multi-layered vector design based on pre-calculated paths.
        
        --- 🎨 LAYERED GEOMETRY INSTRUCTIONS ---
        I have calculated 3 interlocking paths for the footer. You MUST use them to create the "Emerging Layers" effect.
        
        1. **Layer 1 (Back)**: Use Path: "{bottom_layers.get('layer_back')}"
           - Fill: Lightest shade of the primary color (opacity 0.2).
        2. **Layer 2 (Middle)**: Use Path: "{bottom_layers.get('layer_mid')}"
           - Fill: Medium shade (opacity 0.6).
        3. **Layer 3 (Front)**: Use Path: "{bottom_layers.get('layer_front')}"
           - Fill: Darkest/Strongest shade (opacity 1.0).
           - This creates the 3D depth effect.
        
        --- 📝 TEXT LAYOUT & CONTRAST (ZERO TOLERANCE) ---
        1. **Safe Zone**: ALL Text must be inside a transparent box from Y={text_zone_y_start} to Y={safe_y_bottom}.
           - DO NOT place text overlapping the footer waves.
        
        2. **Alignment & Flow**:
           - Use HTML/CSS inside <foreignObject>:
             <div style="width: 100%; height: {text_zone_height}px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
               ...content...
             </div>
           - For lists, use `text-align: right` (RTL) with proper padding.
        
        3. **Contrast**:
           - Background is White/Light -> Text MUST be #111111 or #0F172A.
           - Footer is Dark -> Text inside footer (if any) MUST be #FFFFFF.
        
        INPUT DATA:
        - Request: "{user_msg}"
        - ViewBox: 0 0 {width} {height}
        
        OUTPUT:
        - Return ONLY raw SVG code.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=0.6)
        )

        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        if '<svg' in svg_output and 'xmlns=' not in svg_output:
            svg_output = svg_output.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
            
        return jsonify({"response": svg_output})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
