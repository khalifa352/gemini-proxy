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

# --- 🧠 محرك المنحنيات المتغيرة (Variable Math Engine) ---
def generate_dynamic_waves(width, height):
    """
    يولد منحنيات احترافية لكن يغير شكلها في كل مرة (Random Seed).
    """
    w = int(width)
    h = int(height)
    
    # 🎲 1. العشوائية المدروسة (Controlled Randomness)
    # نغير ارتفاع الموجة ومكان القمة في كل مرة
    amp_factor = random.uniform(0.15, 0.30)  # ارتفاع بين 15% و 30%
    amplitude = int(h * amp_factor)
    
    # نغير اتجاه الانحناء (يسار أو يمين)
    direction = random.choice([-1, 1]) 
    
    # نقاط التحكم
    start_y = h - int(amplitude * 0.8)
    end_y = h - int(amplitude * 0.4)
    
    # تحريك نقاط التحكم أفقياً وعمودياً للتنوع
    cp1_x = int(w * (0.3 + (random.uniform(-0.1, 0.1))))
    cp1_y = h - int(amplitude * (1.5 if direction == 1 else 0.5))
    
    cp2_x = int(w * (0.7 + (random.uniform(-0.1, 0.1))))
    cp2_y = h - int(amplitude * (0.1 if direction == 1 else 1.2))

    # 🌊 2. توليد الطبقات
    # الطبقة الخلفية (Layer 1)
    path_back = f"M0,{h} L0,{start_y} C{cp1_x},{cp1_y} {cp2_x},{cp2_y} {w},{end_y} L{w},{h} Z"
    
    # الطبقة الوسطى (Layer 2) - إزاحة بسيطة
    path_mid = f"M0,{h} L0,{start_y+30} C{cp1_x+30},{cp1_y+20} {cp2_x-30},{cp2_y+20} {w},{end_y+30} L{w},{h} Z"
    
    # الطبقة الأمامية (Layer 3) - إزاحة أكبر
    path_front = f"M0,{h} L0,{start_y+60} C{cp1_x+60},{cp1_y+50} {cp2_x-60},{cp2_y+50} {w},{end_y+60} L{w},{h} Z"
    
    # 🛡️ 3. حساب المنطقة الآمنة
    top_limit = min(start_y, end_y, cp1_y, cp2_y)
    safe_bottom = top_limit - 60  # هامش أمان
    
    return {
        "back": path_back,
        "mid": path_mid,
        "front": path_front
    }, safe_bottom

# --- جلب الوصفات ---
def get_recipe_data(category_name, user_prompt):
    # (نفس دالة البحث السابقة)
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()
    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json",
        "brochure": "print/brochures.json",
        "menu": "print/menus.json",
        "invoice": "print/invoices.json"
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
            # هنا نختار وصفة عشوائية أو حسب الطلب من القائمة
            if isinstance(raw, list):
                # فلترة بسيطة أو اختيار عشوائي للتنوع
                return random.choice(raw) 
            return raw
    except: return {}

@app.route('/')
def home(): return "Hybrid Engine: Math Curves + Recipe Colors 🎨📐"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Error"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        # 1. جلب الوصفة (بما فيها الألوان والستايل)
        recipe = get_recipe_data(cat_name, user_msg)
        
        # استخراج الألوان من الوصفة (أهم خطوة!)
        # إذا لم توجد ألوان، نستخدم قيم افتراضية
        visual_style = recipe.get('visual_style', {})
        colors = recipe.get('generative_rules', {}).get('palette_suggestions', ["#1a237e + #ffffff + #ff6f00"])
        
        # 2. توليد المنحنيات الرياضية (بشكل متغير كل مرة)
        waves, safe_bottom = generate_dynamic_waves(width, height)
        text_zone_height = safe_bottom - 50

        # 3. بناء التعليمات الهجينة
        sys_instructions = f"""
        Role: Senior Art Director.
        Task: Create a vivid, professional design merging PRE-CALCULATED CURVES with RECIPE COLORS.
        
        --- 🎨 SOURCE RECIPE (STYLE GUIDE) ---
        Recipe ID: {recipe.get('id', 'Dynamic')}
        Description: {recipe.get('description', 'Professional Design')}
        SUGGESTED PALETTE: {json.dumps(colors)}
        
        --- 📐 GEOMETRY & LAYOUT (MANDATORY) ---
        Use these exact math-generated paths for the footer waves:
        1. **Layer 1 (Back)**: Path="{waves['back']}"
           - COLOR: Use the LIGHTEST/SOFTEST color from the palette (Opacity 0.3).
        2. **Layer 2 (Mid)**:  Path="{waves['mid']}"
           - COLOR: Use a SECONDARY color or medium shade (Opacity 0.7).
        3. **Layer 3 (Front)**: Path="{waves['front']}"
           - COLOR: Use the PRIMARY/DARKEST brand color (Opacity 1.0).
           - This layer must look solid and define the bottom edge.
           
        --- 📝 CONTENT & SAFETY ---
        - **Safe Zone**: Text must be between Y=0 and Y={safe_bottom}.
        - **No Overlap**: Do not place text on top of the footer waves.
        - **Contrast**: 
           - If using Dark Background recipe -> White Text.
           - If using Light Background recipe -> Dark Text.
        
        INPUT:
        - Request: "{user_msg}"
        - ViewBox: 0 0 {width} {height}
        
        OUTPUT:
        - Return ONLY raw SVG code.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=0.9) # حرارة عالية للتنوع
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
