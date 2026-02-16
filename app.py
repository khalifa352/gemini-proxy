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

# --- 📐 مكتبة الأشكال الهندسية (The Geometry Library) ---

def geo_smooth_waves(width, height):
    """ يولد موجات ناعمة (للتصاميم الطبية، التجميل، الحديثة) """
    w, h = int(width), int(height)
    amp = int(h * random.uniform(0.15, 0.25))
    
    # نقاط تحكم عشوائية لكسر التكرار
    direction = random.choice([-1, 1])
    p_start = h - int(amp * 0.8)
    p_end = h - int(amp * 0.4)
    cp1 = (int(w * 0.3), h - int(amp * (1.5 if direction==1 else 0.5)))
    cp2 = (int(w * 0.7), h - int(amp * (0.1 if direction==1 else 1.2)))
    
    path_back = f"M0,{h} L0,{p_start} C{cp1[0]},{cp1[1]} {cp2[0]},{cp2[1]} {w},{p_end} L{w},{h} Z"
    path_front = f"M0,{h} L0,{p_start+60} C{cp1[0]+60},{cp1[1]+50} {cp2[0]-60},{cp2[1]+50} {w},{p_end+60} L{w},{h} Z"
    
    return {"back": path_back, "front": path_front}, min(p_start, p_end, cp1[1], cp2[1]) - 50

def geo_sharp_polygons(width, height):
    """ يولد أشكالاً حادة ومضلعات (للشركات، العقارات، المقاولات) """
    w, h = int(width), int(height)
    peak = h - int(h * 0.3)
    
    # مثلث قاطع حاد
    x_peak = int(w * random.uniform(0.2, 0.8))
    
    path_back = f"M0,{h} L0,{peak} L{x_peak},{peak-100} L{w},{peak} L{w},{h} Z"
    path_front = f"M0,{h} L0,{peak+50} L{x_peak},{peak-50} L{w},{peak+50} L{w},{h} Z"
    
    return {"back": path_back, "front": path_front}, peak - 120

def geo_modern_slant(width, height):
    """ يولد قطعاً مائلاً بسيطاً (للتصاميم الرسمية والبسيطة) """
    w, h = int(width), int(height)
    start_y = h - int(h * 0.2)
    end_y = h - int(h * 0.1)
    
    # مجرد خط مائل نظيف
    path_back = f"M0,{h} L0,{start_y} L{w},{end_y} L{w},{h} Z"
    path_front = f"M0,{h} L0,{start_y+40} L{w},{end_y+40} L{w},{h} Z"
    
    return {"back": path_back, "front": path_front}, min(start_y, end_y) - 50

# --- 🧠 الموجه الذكي (The Router) ---
def generate_geometry_by_style(style_type, width, height):
    """ يختار الدالة المناسبة بناءً على نوع الوصفة """
    if "corporate" in style_type or "sharp" in style_type or "real_estate" in style_type:
        return geo_sharp_polygons(width, height), "SHARP_POLYGONS"
    elif "minimal" in style_type or "clean" in style_type:
        return geo_modern_slant(width, height), "MODERN_SLANT"
    else:
        # الافتراضي للمنحنيات
        return geo_smooth_waves(width, height), "SMOOTH_WAVES"

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
            if isinstance(raw, list): return random.choice(raw)
            return raw
    except: return {}

@app.route('/')
def home(): return "Almonjez: Polymorphic Geometry Engine 📐🎨"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Error"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        # 1. جلب الوصفة
        recipe = get_recipe_data(cat_name, user_msg)
        
        # معرفة "نوع" الوصفة لتحديد الشكل الهندسي
        # نبحث في الـ tags أو الـ description أو الـ id
        recipe_context = (recipe.get('id', '') + recipe.get('suitable_for', '') + str(recipe.get('tags', []))).lower()
        
        # 2. بايثون يختار "القلم" المناسب (موجة؟ مثلث؟ خط مائل؟)
        paths, geo_type = generate_geometry_by_style(recipe_context, width, height)
        safe_bottom = paths[1] # القيمة الثانية هي المنطقة الآمنة

        # 3. التعليمات (ديناميكية حسب الشكل المختار)
        sys_instructions = f"""
        Role: Senior Designer.
        Task: Apply the selected recipe style onto the pre-calculated geometry.
        
        --- 📐 GEOMETRY MODE: {geo_type} ---
        Python has generated these specific footer paths for you:
        1. **Background Layer**: Path="{paths[0]['back']}" (Opacity 0.3)
        2. **Foreground Layer**: Path="{paths[0]['front']}" (Opacity 1.0)
        
        --- 🎨 RECIPE STYLE ---
        - ID: {recipe.get('id')}
        - Colors: Use the recipe's palette. If {geo_type} is SHARP, use high contrast. If WAVES, use gradients.
        
        --- 📝 LAYOUT RULES ---
        - **Safe Zone**: Text must end at Y={safe_bottom}.
        - **Contrast**: Strict Dark/Light rules apply.
        - **Alignment**: Justify text for professional look.
        
        INPUT:
        - Content: "{user_msg}"
        - ViewBox: 0 0 {width} {height}
        
        OUTPUT:
        - Return ONLY raw SVG code.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions, temperature=0.8)
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
