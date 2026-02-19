import os
import json
import logging
import random
import re
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ CONFIGURATION & SYSTEM SETUP (ALMONJEZ V21)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Dynamic_Blueprint")

app = Flask(__name__)

# مسارات مكتبة الوصفات الخاصة بك
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(BASE_DIR, 'recipes', 'core')

# ======================================================
# 🔌 AI CLIENT (GEMINI 2.0 FLASH)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ V21 Dynamic Engine Connected.")
except Exception as e:
    logger.error(f"❌ AI Init Error: {e}")

# ======================================================
# 📂 1. THE ASSET VAULT (مدير المكتبة)
# ======================================================
class AssetVault:
    def __init__(self):
        self.layouts = []
        self.refresh_library()

    def refresh_library(self):
        """قراءة قوالبك الحقيقية من layout_sets.json"""
        try:
            layout_file = os.path.join(CORE_PATH, 'layout_sets.json')
            if os.path.exists(layout_file):
                with open(layout_file, 'r', encoding='utf-8') as f:
                    self.layouts = json.load(f)
                logger.info(f"📚 Loaded {len(self.layouts)} dynamic layouts.")
            else:
                logger.error("❌ layout_sets.json not found! Using fallback.")
                self.layouts = self.get_fallback_layout()
        except Exception as e:
            logger.error(f"❌ Library Sync Error: {e}")
            self.layouts = self.get_fallback_layout()

    def find_best_match(self, user_msg):
        """مطابقة ذكية للـ Vibes لضمان التنوع"""
        msg = user_msg.lower()
        candidates = [l for l in self.layouts if any(v in msg for v in l.get('vibes', []))]
        return random.choice(candidates if candidates else self.layouts)
        
    def get_fallback_layout(self):
        return [{
            "id": "fallback", "logic": {"text_safe_area": {"top": 100, "left": 40, "right": 40, "bottom": 100}},
            "structure": {"viewBox": "0 0 595 842", "layers": [{"d_base": "M0 0 L595 0 L595 200 C300 300 100 100 0 200 Z", "fill": "{{COLOR_1}}", "opacity": 1.0}]},
            "params": {}
        }]

GLOBAL_VAULT = AssetVault()

# ======================================================
# 🧹 2. THE SANITIZER LAYER (حماية الـ JSON)
# ======================================================
class Sanitizer:
    @staticmethod
    def parse_json(raw_text):
        try:
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not match: return None
            json_str = re.sub(r',\s*([\]}])', r'\1', match.group(0))
            return json.loads(json_str)
        except: return None

# ======================================================
# 🔤 3. THE TEXT ENGINE (محرك النصوص الصارم لـ iOS)
# ======================================================
class TextEngine:
    @staticmethod
    def build_foreign_object(x, y, w, h, text, font_size, max_lines, color, weight="normal"):
        return f"""
        <foreignObject x="{x}" y="{y}" width="{w}" height="{h}">
            <div xmlns="http://www.w3.org/1999/xhtml" style="
                direction: rtl; 
                text-align: right; 
                color: {color}; 
                font-family: 'Cairo', 'Tajawal', 'Arial', sans-serif;
                font-size: {font_size}px;
                font-weight: {weight};
                line-height: 1.4;
                margin: 0;
                padding: 0;
                overflow: hidden;
                display: -webkit-box;
                -webkit-line-clamp: {max_lines};
                -webkit-box-orient: vertical;
            ">
                {text}
            </div>
        </foreignObject>
        """

# ======================================================
# 📐 4. THE GEOMETRY RESOLVER (محرك التنوع الهندسي)
# ======================================================
class GeometryResolver:
    @staticmethod
    def build_layout(layout, ai_data):
        """
        هنا يحدث التنوع الحقيقي!
        يقوم بحل الـ min/max عشوائياً ويطبق ألوان الذكاء الاصطناعي.
        """
        # 1. التنوع الهندسي (حل الـ Params)
        params = {}
        for key, limits in layout.get('params', {}).items():
            params[key] = str(random.randint(limits.get('min', 0), limits.get('max', 100)))

        # 2. حقن الألوان والـ Params في الطبقات
        viewBox = layout.get('structure', {}).get('viewBox', '0 0 595 842')
        defs = "".join(layout.get('structure', {}).get('defs', []))
        
        # استبدال الألوان في Defs (التدرجات)
        defs = defs.replace("{{COLOR_1}}", ai_data.get("primary", "#1A237E"))
        defs = defs.replace("{{COLOR_2}}", ai_data.get("accent", "#FF5252"))

        paths_svg = ""
        for layer in layout.get('structure', {}).get('layers', []):
            element_type = layer.get('element', 'path')
            fill = layer.get('fill', '#000')
            fill = fill.replace("{{COLOR_1}}", ai_data.get("primary", "#1A237E"))
            fill = fill.replace("{{COLOR_2}}", ai_data.get("accent", "#FF5252"))
            opacity = layer.get('opacity', 1.0)
            
            if element_type == 'path':
                d = layer.get('d_base', '')
                for p_key, p_val in params.items():
                    d = d.replace(f"{{{{{p_key}}}}}", p_val)
                paths_svg += f'<path d="{d}" fill="{fill}" opacity="{opacity}" />\n'
            elif element_type == 'circle':
                cx, cy, r = layer.get('cx', '0'), layer.get('cy', '0'), layer.get('r', '0')
                paths_svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" opacity="{opacity}" />\n'

        # 3. حساب مناطق النصوص بناءً على Safe Area
        safe_area = layout.get('logic', {}).get('text_safe_area', {})
        top = safe_area.get('top', 100)
        left = safe_area.get('left', 40)
        right = safe_area.get('right', 40)
        
        # العرض الفعلي مأخوذ من viewBox 0 0 W H
        w_match = re.search(r'0 0 (\d+) (\d+)', viewBox)
        canvas_w = int(w_match.group(1)) if w_match else 595
        canvas_h = int(w_match.group(2)) if w_match else 842
        
        text_w = canvas_w - left - right
        
        # توزيع مساحات النصوص
        texts_svg = ""
        texts_svg += TextEngine.build_foreign_object(
            x=left, y=top, w=text_w, h=100,
            text=ai_data.get("title", "عنوان التصميم"),
            font_size=42, max_lines=2, color=ai_data.get("text_color_title", "#111111"), weight="bold"
        )
        texts_svg += TextEngine.build_foreign_object(
            x=left, y=top + 120, w=text_w, h=canvas_h - top - 180,
            text=ai_data.get("body", "التفاصيل..."),
            font_size=22, max_lines=15, color=ai_data.get("text_color_body", "#444444"), weight="normal"
        )

        # 4. التجميع النهائي للـ SVG
        final_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xhtml="http://www.w3.org/1999/xhtml" viewBox="{viewBox}" width="100%" height="100%">
            <defs>{defs}</defs>
            {paths_svg}
            {texts_svg}
        </svg>"""

        return re.sub(r'>\s+<', '><', final_svg.strip())

# ======================================================
# 🚀 5. THE PRODUCTION ROUTE
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V21 Dynamic Engine Online 🍏", "layouts": len(GLOBAL_VAULT.layouts)})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        
        # 1. اختيار القالب الديناميكي من مكتبتك
        layout = GLOBAL_VAULT.find_best_match(user_msg)
        
        # 2. توجيه جيميني لكتابة الـ JSON فقط (بدون أي SVG)
        system_instruction = f"""
        ROLE: Expert Art Director & Copywriter.
        TASK: Extract intent and return strictly a JSON object.
        
        === 🎨 COLOR STRATEGY ===
        - "primary": Main hex color based on request vibes.
        - "accent": Complementary hex color.
        - "text_color_title": Hex color (must contrast with background, e.g. #FFFFFF or #111111).
        - "text_color_body": Hex color for readable body text.
        
        === 📝 TEXT BUDGET ===
        - "title": Punchy title (max 6 words).
        - "body": Professional details (max 40 words).
        
        === ✅ OUTPUT FORMAT (JSON ONLY) ===
        {{
            "primary": "#HEX",
            "accent": "#HEX",
            "text_color_title": "#HEX",
            "text_color_body": "#HEX",
            "title": "...",
            "body": "..."
        }}
        """

        # 3. استدعاء جيميني (سريع جداً!)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.7) # حرارة 0.7 لضمان تنوع الألوان والنصوص
        )
        
        # 4. التعقيم (Sanitize)
        ai_data = Sanitizer.parse_json(response.text)
        if not ai_data:
            return jsonify({"error": "Failed to parse AI Contract."}), 500
            
        # 5. التجميع الديناميكي (Geometry + AI Colors/Texts)
        final_svg = GeometryResolver.build_layout(layout, ai_data)

        return jsonify({
            "response": final_svg,
            "meta": {
                "engine": "V21_Dynamic_Assembler",
                "layout_id": layout.get('id', 'unknown'),
                "ai_contract": ai_data
            }
        })

    except Exception as e:
        logger.error(f"Assembly Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
