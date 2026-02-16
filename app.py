import os
import json
import logging
import random
import math
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- مكتبة Google ---
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
except: pass

# --- 🧠 محرك الرياضيات (The CurveKit Engine) ---
def generate_complex_wave(width, height, position='bottom', complexity=3):
    """
    يولد مسار SVG معقد (مثل الأمثلة التي أرسلتها) بدلاً من منحنى بسيط.
    """
    points = []
    segment_width = width / complexity
    
    # نقطة البداية
    if position == 'bottom':
        start_y = height * 0.8
        path = f"M0,{start_y}"
        
        for i in range(complexity):
            cp1_x = (i * segment_width) + (segment_width * 0.3)
            cp1_y = start_y + random.randint(-50, 50)
            
            cp2_x = (i * segment_width) + (segment_width * 0.7)
            cp2_y = start_y + random.randint(-50, 50)
            
            end_x = (i + 1) * segment_width
            end_y = start_y + random.randint(-20, 20)
            
            path += f" C{cp1_x},{cp1_y} {cp2_x},{cp2_y} {end_x},{end_y}"
            
        # إغلاق الشكل
        path += f" L{width},{height} L0,{height} Z"
        return path
        
    elif position == 'top':
        start_y = height * 0.2
        path = f"M0,{start_y}"
        
        for i in range(complexity):
            cp1_x = (i * segment_width) + (segment_width * 0.3)
            cp1_y = start_y + random.randint(-40, 40)
            
            cp2_x = (i * segment_width) + (segment_width * 0.7)
            cp2_y = start_y + random.randint(-40, 40)
            
            end_x = (i + 1) * segment_width
            end_y = start_y + random.randint(-15, 15)
            
            path += f" C{cp1_x},{cp1_y} {cp2_x},{cp2_y} {end_x},{end_y}"
            
        path += f" L{width},0 L0,0 Z"
        return path
    
    return ""

# --- الدوال المساعدة ---
def get_design_rules(category_name, user_prompt):
    # (نفس كود جلب الملفات السابق - لا تغيير)
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()
    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json",
        "brochure": "print/brochures.json",
        "menu": "print/menus.json",
        "invoice": "print/invoices.json",
        "certificate": "print/certificates.json"
    }
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
            if isinstance(raw, list): return raw
            if isinstance(raw, dict): return [raw]
    except: return []
    return []

@app.route('/')
def home(): return "CurveKit Engine Active 🌊"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Client Error"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        # 1. جلب القواعد
        available_rules = get_design_rules(cat_name, user_msg)
        
        # 2. توليد "أصول" رياضية (Pre-calculated Assets)
        # هنا السحر: نحن نعطي جيميني الكود الجاهز للمنحنى بدلاً من أن نطلب منه تخيله
        curve_top = generate_complex_wave(width, height, 'top')
        curve_bottom = generate_complex_wave(width, height, 'bottom')
        
        sys_instructions = f"""
        Role: Senior SVG Engineer.
        Task: Create a High-End Design with strict WHITESPACE and COMPLEX CURVES.
        
        --- CRITICAL ASSETS (USE THESE PATHS) ---
        I have pre-calculated professional Bezier curves for you. YOU MUST USE THEM if the design needs curves.
        > Top Curve Path: "{curve_top}"
        > Bottom Curve Path: "{curve_bottom}"
        
        --- DESIGN RULES ---
        1. WHITESPACE (Negative Space):
           - Keep at least 40% of the canvas EMPTY (White or light grey).
           - Do NOT fill every corner. Let the design breathe.
           - Text must have padding (at least 60px from edges).
        
        2. LAYERING:
           - Draw the 'Top Curve Path' with a primary color.
           - Draw it AGAIN underneath with slight opacity (0.3) and scale (1.05) to create the "Layered" effect seen in professional examples.
        
        3. TYPOGRAPHY:
           - Use <foreignObject> for all text.
           - Title: Bold, Large (48px+), Dark Color.
           - Body: Clean, Line-height 1.6, Grey Color.
        
        4. COLOR PALETTE:
           - Extract mood from request.
           - Use Gradients (<linearGradient>) for the curves to make them look 3D.
        
        INPUT DATA:
        - Request: "{user_msg}"
        - ViewBox: 0 0 {width} {height}
        - Catalog: {json.dumps(available_rules)}
        
        OUTPUT:
        - Return ONLY raw SVG code.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=0.7)
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
