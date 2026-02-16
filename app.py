import os
import json
import logging
import random
import math
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Google Client Setup ---
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        logger.info("✅ GenAI Connected (Professional Mode)")
except: pass

# --- 🧠 محرك الرياضيات الاحترافي (Pro Smooth Curve Engine) ---
def generate_smooth_wave(width, height, position='bottom', complexity=2, amplitude_ratio=0.15):
    """
    يولد موجات بيزير انسيابية تماماً (Perfectly Smooth Cubic Bezier).
    يضمن استمرارية المماس (C1 Continuity) لمنع التشوه.
    يرجع المسار + أقصى ارتفاع وصل إليه (لحساب المنطقة الآمنة).
    """
    amplitude = height * amplitude_ratio
    
    if position == 'bottom':
        base_y = height - (amplitude * 1.5) # خط الأساس
        path = f"M0,{height} L0,{base_y}"
        max_y_reached = base_y - amplitude # لتقريب منطقة الخطر
        
        segment_width = width / complexity
        
        for i in range(complexity):
            start_x = i * segment_width
            end_x = (i + 1) * segment_width
            
            # تبديل الاتجاه (موجة فوق وموجة تحت)
            direction = 1 if i % 2 == 0 else -1
            
            # نقاط التحكم لضمان النعومة
            cp1_x = start_x + (segment_width * 0.5)
            cp1_y = base_y + (direction * amplitude)
            
            cp2_x = end_x - (segment_width * 0.5)
            cp2_y = base_y - (direction * amplitude)
            
            # نقطة النهاية تعود لخط الأساس
            path += f" C{cp1_x},{cp1_y} {cp2_x},{cp2_y} {end_x},{base_y}"
            
        path += f" L{width},{height} L0,{height} Z"
        # ارتفاع المنطقة المشغولة من الأسفل
        occupied_height = height - max_y_reached + 50 # 50px هامش أمان
        return path, occupied_height

    elif position == 'top':
        base_y = amplitude * 1.5
        path = f"M0,0 L0,{base_y}"
        max_y_reached = base_y + amplitude

        segment_width = width / complexity
        for i in range(complexity):
            start_x = i * segment_width
            end_x = (i + 1) * segment_width
            direction = -1 if i % 2 == 0 else 1 # عكس الاتجاه للعلوي
            
            cp1_x = start_x + (segment_width * 0.5)
            cp1_y = base_y + (direction * amplitude)
            cp2_x = end_x - (segment_width * 0.5)
            cp2_y = base_y - (direction * amplitude)
            
            path += f" C{cp1_x},{cp1_y} {cp2_x},{cp2_y} {end_x},{base_y}"
            
        path += f" L{width},0 L0,0 Z"
        occupied_height = max_y_reached + 50 # 50px هامش أمان
        return path, occupied_height
        
    return "", 0

# --- Helper Functions (Catalog Fetcher) ---
def get_design_rules(category_name, user_prompt):
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
def home(): return "Almonjez Pro Engine: Smooth Curves & Safe Zones Active 🛡️🌊"

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
        
        # 2. توليد الأصول الرياضية + حساب مناطق الأمان
        # نولد منحنيات بدرجات تعقيد مختلفة
        curve_top_simple, top_h1 = generate_smooth_wave(width, height, 'top', complexity=1, amplitude_ratio=0.2)
        curve_top_complex, top_h2 = generate_smooth_wave(width, height, 'top', complexity=3, amplitude_ratio=0.15)
        
        curve_bottom_simple, bottom_h1 = generate_smooth_wave(width, height, 'bottom', complexity=1, amplitude_ratio=0.2)
        curve_bottom_complex, bottom_h2 = generate_smooth_wave(width, height, 'bottom', complexity=3, amplitude_ratio=0.15)
        
        # تحديد حدود المنطقة الآمنة للنص
        safe_top_y = max(top_h1, top_h2) + 40 # هامش إضافي
        safe_bottom_y = height - max(bottom_h1, bottom_h2) - 40 # هامش إضافي
        safe_height = safe_bottom_y - safe_top_y

        # 3. التعليمات الصارمة الجديدة
        sys_instructions = f"""
        Role: Senior SVG Specialist & Layout Engineer.
        Task: Create a professional design with PERFECT curves, STRICT safe zones, and HIGH contrast.
        
        --- 🛡️ CRITICAL LAYOUT RULES (DO NOT BREAK) ---
        1. CONTENT SAFE ZONE:
           - ALL text and main content MUST be placed between Y={safe_top_y} and Y={safe_bottom_y}.
           - Absolutely NO text is allowed in the top header area (Y < {safe_top_y}) or the bottom footer area (Y > {safe_bottom_y}). These areas are for graphics only.
        
        2. COLOR CONTRAST PROTOCOL:
           - IF background is DARK (e.g., Blue, Green, Black) -> Text MUST be WHITE (#FFFFFF).
           - IF background is LIGHT (e.g., White, Light Grey) -> Text MUST be DARK BLACK (#000000 or #111111).
           - NEVER use low contrast combinations like Blue text on Green background.
        
        3. TYPOGRAPHY & KASHEEDA:
           - Use <foreignObject> for ALL text.
           - For body paragraphs/lists, use CSS: `text-align: justify;` to create a formal Arabic look.
           - Title fonts must be large and bold.
        
        --- 🌊 GEOMETRY ASSETS (PRE-CALCULATED) ---
        Use these paths for professional, smooth curves. Do not draw your own messy curves.
        - Simple Top Wave: "{curve_top_simple}"
        - Complex Top Wave: "{curve_top_complex}"
        - Simple Bottom Wave: "{curve_bottom_simple}"
        - Complex Bottom Wave: "{curve_bottom_complex}"
        
        INSTRUCTIONS:
        - Analyze the user request and the design catalog.
        - Select the best curves from the assets above. You can layer them with opacity.
        - Draw the background first, then curves, then text in the Safe Zone.
        
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
