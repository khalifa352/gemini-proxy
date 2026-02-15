import os
import json
import logging
from flask import Flask, request, jsonify

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- محاولة استيراد المكتبة ---
client = None
try:
    from google import genai
    from google.genai import types
    
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        logger.info("✅ Google GenAI Client Connected")
    else:
        logger.warning("⚠️ API Key missing")
except Exception as e:
    logger.error(f"❌ Library Error: {e}")

# --- دالة جلب الوصفات ---
def get_recipe_lenient(category_name, user_prompt):
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
    
    for key, path in flexible_map.items():
        if key in cat or key in prompt:
            full_path = os.path.join(base_path, path)
            if os.path.exists(full_path): return full_path
            
    return os.path.join(base_path, "print/flyers.json")

@app.route('/')
def home(): return "Almonjez Engine: Ready to Design 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Server Error: Client failed"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        logger.info(f"📥 Request: {cat_name} ({width}x{height})")

        # 1. جلب الوصفة
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        recipe_data = {}
        if os.path.exists(recipe_path):
            try:
                with open(recipe_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    recipe_data = raw[0] if isinstance(raw, list) else raw
            except: pass

        # 2. أبعاد الرسم
        view_box = recipe_data.get('canvas_size', {}).get('viewBox', f'0 0 {width} {height}')

        # 🧠 التعليمات الصارمة (Full Bleed + Contrast)
        sys_instructions = f"""
        Role: Senior Graphic Designer.
        Task: Create a 'Full Bleed' SVG design.
        
        RULE 1: NO WHITE MARGINS (Full Background)
        - The very first element MUST be a <rect> or <image> that covers 100% of the canvas.
        - Syntax: <rect x="0" y="0" width="100%" height="100%" fill="THEME_COLOR" />
        - Do NOT leave any whitespace around the edges.
        
        RULE 2: TEXT VISIBILITY (High Contrast)
        - If Background is Dark -> Text MUST be White (#FFFFFF).
        - If Background is Light -> Text MUST be Black (#000000).
        - NEVER place light text on light background.
        
        RULE 3: HTML TEXT ENGINE (For Arabic)
        - ALWAYS use <foreignObject> for text.
        - Syntax:
          <foreignObject x="5%" y=".." width="90%" height="100">
             <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right; font-family:sans-serif; font-weight:bold; color:CONTRAST_COLOR;">
                CONTENT
             </div>
          </foreignObject>
        
        RULE 4: DESIGN ELEMENTS
        - Use the JSON Blueprint to draw shapes/layout.
        - Make it look premium and filled with content.
        
        Blueprint: {json.dumps(recipe_data)}
        """

        # التوليد
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions)
        )

        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        
        # تصحيح إضافي: التأكد من وجود xmlns في الـ SVG لضمان العرض
        if '<svg' in svg_output and 'xmlns=' not in svg_output:
            svg_output = svg_output.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
            
        return jsonify({"response": svg_output})

    except Exception as e:
        logger.error(f"‼️ Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
