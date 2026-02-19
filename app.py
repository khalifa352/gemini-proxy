import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ CONFIGURATION & SYSTEM SETUP (ALMONJEZ V22 - AI ARTIST)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_AI_Artist")

app = Flask(__name__)

# مسارات مكتبة الوصفات الخاصة بك
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(BASE_DIR, 'recipes', 'core')

# ======================================================
# 🔌 AI CLIENT (GEMINI 2.0 FLASH ONLY)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ V22 AI Artist Engine Connected (Flash 2.0).")
except Exception as e:
    logger.error(f"❌ AI Init Error: {e}")

# ======================================================
# 📂 1. THE ASSET VAULT (لقراءة الإلهام والألوان)
# ======================================================
class AssetVault:
    def __init__(self):
        self.layouts = []
        self.colors = []
        self.typography = {}
        self.refresh_library()

    def refresh_library(self):
        try:
            layout_file = os.path.join(CORE_PATH, 'layout_sets.json')
            colors_file = os.path.join(CORE_PATH, 'colors.json')
            typo_file = os.path.join(CORE_PATH, 'typography.json')

            if os.path.exists(layout_file):
                with open(layout_file, 'r', encoding='utf-8') as f:
                    self.layouts = json.load(f)
            
            if os.path.exists(colors_file):
                with open(colors_file, 'r', encoding='utf-8') as f:
                    self.colors = json.load(f)
                    
            if os.path.exists(typo_file):
                with open(typo_file, 'r', encoding='utf-8') as f:
                    self.typography = json.load(f)

        except Exception as e:
            logger.error(f"❌ Library Sync Error: {e}")

    def find_best_match(self, user_msg):
        msg = user_msg.lower()
        candidates = [l for l in self.layouts if any(v in msg for v in l.get('vibes', []))]
        return random.choice(candidates if candidates else self.layouts) if self.layouts else {}

    def get_random_palette(self):
        return random.choice(self.colors) if self.colors else ["#1A237E", "#E8EAF6", "#FF5252"]

GLOBAL_VAULT = AssetVault()

# ======================================================
# 🧹 2. EXTRACTION HELPERS
# ======================================================
def extract_pure_svg(raw_text):
    match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
    return match.group(0) if match else None

def extract_plan(raw_text):
    match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL | re.IGNORECASE)
    if not match: return {}
    try: return json.loads(match.group(1))
    except: return {}

# ======================================================
# 🚀 3. THE PRODUCTION ROUTE
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V22 AI Artist Online 🎨", "message": "Gemini has full drawing control."})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        # 1. إعطاء جيميني "الإلهام" من مكتبتك بدلاً من إجباره على الكود
        layout_inspiration = GLOBAL_VAULT.find_best_match(user_msg)
        palette = GLOBAL_VAULT.get_random_palette()
        safe_area = layout_inspiration.get('logic', {}).get('text_safe_area', {'top': 50, 'bottom': 50, 'left': 40, 'right': 40})
        vibes = layout_inspiration.get('vibes', ['modern', 'creative'])
        
        # 2. بناء "توجيه المدير الفني"
        system_instruction = f"""
        ROLE: Master SVG Artist & UI/UX Designer.
        MODEL: Gemini 2.0 Flash (Creative Mode).

        === 🎨 CREATIVE FREEDOM (YOU DRAW EVERYTHING) ===
        You are completely responsible for drawing the SVG. I want BEAUTIFUL, highly professional, and creative shapes.
        - If the vibe is 'organic' or 'medical', draw smooth, elegant bezier curves (<path d="M... C...">).
        - If the vibe is 'corporate' or 'tech', draw sharp, dynamic polygons or sleek gradients.
        - DO NOT make it look ugly or generic. Use your artistic intelligence.
        - Make full use of `<defs>` for stunning gradients or shadows.
        
        === 🎯 DESIGN INSPIRATION ===
        - Requested Vibe: {', '.join(vibes)}
        - Color Palette: {json.dumps(palette)} (Use these creatively for backgrounds, accents, and text).
        - Canvas Size: {width}x{height}
        
        === 📱 iOS STRICT REQUIREMENT (NON-NEGOTIABLE) ===
        Because this design will render in an iOS WKWebView, you MUST handle text like this:
        1. Keep all text within this Safe Area: Top {safe_area.get('top')}px, Bottom {safe_area.get('bottom')}px, Left/Right {safe_area.get('left')}px.
        2. **FOREIGN OBJECTS ONLY**: You MUST use `<foreignObject>` for all text to allow auto-wrapping.
        3. Inside `<foreignObject>`, use `<div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right;">`.
        
        Example of correct text:
        <foreignObject x="40" y="100" width="{width - 80}" height="200">
            <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right; color:#FFFFFF; font-family:'Cairo', sans-serif;">
                <h1 style="font-size:36px; margin:0;">العنوان الجميل</h1>
                <p style="font-size:18px; line-height:1.5;">التفاصيل هنا مع التفاف تلقائي للنص...</p>
            </div>
        </foreignObject>

        === ✅ OUTPUT FORMAT ===
        1. First, output a brief JSON plan (```json ... ```) summarizing your color and shape choices.
        2. Then, output the complete, beautiful `<svg>...</svg>` code.
        """

        # 3. دع جيميني يبدع (حرارة 0.6 تعطي إبداعاً أفضل في الأشكال)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.6 
            )
        )
        
        raw_text = response.text or ""
        
        # 4. استخراج الكود
        final_svg = extract_pure_svg(raw_text)
        plan = extract_plan(raw_text)

        if not final_svg:
             return jsonify({"error": "Gemini failed to generate a valid SVG."}), 500

        # 5. تنظيف ومعالجة لضمان عمله على iOS
        if 'xmlns=' not in final_svg: 
            final_svg = final_svg.replace('<svg', f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%"', 1)
        if '<foreignObject' in final_svg and 'xmlns:xhtml' not in final_svg:
             final_svg = final_svg.replace('<svg', '<svg xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)

        return jsonify({
            "response": final_svg,
            "meta": {
                "engine": "V22_AI_Artist",
                "vibes": vibes,
                "plan": plan
            }
        })

    except Exception as e:
        logger.error(f"Execution Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
