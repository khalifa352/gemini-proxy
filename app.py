import os
import json
import logging
import random
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SYSTEM CONFIGURATION (ALMONJEZ V18.5)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Flash_Engine")

app = Flask(__name__)

# المسارات الحيوية على سيرفر Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(BASE_DIR, 'core')
PRINT_PATH = os.path.join(BASE_DIR, 'recipes', 'print')

# ======================================================
# 🔌 AI CLIENT (GEMINI 2.0 FLASH ONLY)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        # استخدام v1beta للوصول الكامل لخصائص Flash 2.0
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Gemini 2.0 Flash Engine Initialized.")
except Exception as e:
    logger.error(f"❌ AI Init Error: {e}")

# ======================================================
# 📂 1. THE ASSET VAULT (مدير المكتبة الاحترافية)
# ======================================================
class AssetVault:
    def __init__(self):
        self.layouts = []
        self.shapes = []
        self.colors = []
        self.typography = {}
        self.refresh_library()

    def refresh_library(self):
        """قراءة الملفات الحقيقية من المجلدات المرفوعة"""
        try:
            # تحميل Layout Sets
            with open(os.path.join(CORE_PATH, 'layout_sets.json'), 'r', encoding='utf-8') as f:
                self.layouts = json.load(f)
            # تحميل Shape Library
            with open(os.path.join(CORE_PATH, 'shape_library.json'), 'r', encoding='utf-8') as f:
                self.shapes = json.load(f)
            # تحميل الألوان
            with open(os.path.join(CORE_PATH, 'colors.json'), 'r', encoding='utf-8') as f:
                self.colors = json.load(f)
            # تحميل الخطوط
            with open(os.path.join(CORE_PATH, 'typography.json'), 'r', encoding='utf-8') as f:
                self.typography = json.load(f)
            logger.info("📚 Library Synchronized Successfully.")
        except Exception as e:
            logger.error(f"❌ Library Sync Error: {e}")

    def find_best_match(self, user_msg):
        """مطابقة ذكية للـ Vibes بناءً على وصف المستخدم"""
        msg = user_msg.lower()
        candidates = [l for l in self.layouts if any(v in msg for v in l.get('vibes', []))]
        return random.choice(candidates if candidates else self.layouts)

    def get_random_palette(self):
        return random.choice(self.colors) if self.colors else ["#000000", "#FFFFFF"]

GLOBAL_VAULT = AssetVault()

# ======================================================
# 📐 2. THE GEOMETRY RESOLVER (المعالج الهندسي الحتمي)
# ======================================================
class GeometryResolver:
    @staticmethod
    def resolve(layout_set):
        """تحويل الـ Params من نطاق (min/max) إلى أرقام صلبة لضمان الدقة"""
        resolved = {}
        params = layout_set.get('params', {})
        for key, limits in params.items():
            # توليد رقم عشوائي منضبط لكسر التكرار مع الحفاظ على التوازن
            resolved[key] = random.randint(limits['min'], limits['max'])
        return resolved

    @staticmethod
    def inject_assets(svg_skeleton, params, palette):
        """حقن الأرقام والألوان في هيكل الـ SVG"""
        # 1. حقن الألوان
        for i, color in enumerate(palette, 1):
            svg_skeleton = svg_skeleton.replace(f"{{{{COLOR_{i}}}}}", color)
            svg_skeleton = svg_skeleton.replace(f"{{{{ACCENT}}}}", palette[-1])
        
        # 2. حقن القياسات الهندسية
        for key, val in params.items():
            svg_skeleton = svg_skeleton.replace(f"{{{{{key}}}}}", str(val))
        
        return svg_skeleton

# ======================================================
# 🚀 3. THE PRODUCTION ENGINE (V18.5)
# ======================================================
@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Engine Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        
        # --- الخطوة 1: اختيار الوصفة والألوان (المنطق البشري المدفوع بالبايثون) ---
        layout = GLOBAL_VAULT.find_best_match(user_msg)
        palette = GLOBAL_VAULT.get_random_palette()
        params = GeometryResolver.resolve(layout)
        
        # بناء هيكل الطبقات الأساسي
        viewBox = layout['structure'].get('viewBox', '0 0 595 842')
        defs = "".join(layout['structure'].get('defs', []))
        
        layers_html = ""
        for layer in layout['structure'].get('layers', []):
            d = layer.get('d_base', '')
            fill = layer.get('fill', '#000')
            opacity = layer.get('opacity', 1.0)
            layers_html += f'<path d="{d}" fill="{fill}" opacity="{opacity}" />\n'

        # الهيكل الهيكلي الخام
        skeleton = f'<svg viewBox="{viewBox}"><defs>{defs}</defs>{layers_html}</svg>'
        
        # معالجة الهيكل (حقن القيم)
        processed_skeleton = GeometryResolver.inject_assets(skeleton, params, palette)
        
        # --- الخطوة 2: التوجيه الإبداعي لـ Flash 2.0 ---
        safe_area = layout['logic'].get('text_safe_area', {})
        
        system_instruction = f"""
        ROLE: Senior Typographer (Almonjez Pro System).
        MODEL: Gemini 2.0 Flash (Execution Mode).

        === 🏛️ ARCHITECTURAL FRAMEWORK (FIXED) ===
        I have already resolved the professional geometry for '{layout['id']}'.
        DO NOT alter the background paths. You are responsible for the CONTENT LAYER.

        === 📐 DESIGN CONSTRAINTS (HIERARCHY & CONTRAST) ===
        1. Safe Area: Top={safe_area.get('top')}px, Sides={safe_area.get('left', 40)}px.
        2. Hierarchy: Title must be massive and contrast perfectly with background colors.
        3. Alignment: For Arabic text, use `direction="rtl"` and `text-anchor="end"`.
        4. Typography: Use fonts from the library: {json.dumps(GLOBAL_VAULT.typography.get('rtl_default', []))}.

        === 🎨 COLOR CONTEXT ===
        Background Colors used: {json.dumps(palette)}.
        Use high-contrast text colors (e.g., White on Dark, Dark on Light).

        === ✅ OUTPUT ===
        Return ONLY the final SVG code. Integrate the user's message into a compelling design.
        """

        # --- الخطوة 3: التوليد ---
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[f"User Request: {user_msg}\n\nProcessed Skeleton:\n{processed_skeleton}"],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4 # درجة حرارة منخفضة لضمان الانضباط بالقواعد
            )
        )
        
        final_svg = response.text
        # تنظيف المستخرج
        svg_match = re.search(r"(?s)<svg[^>]*>.*?</svg>", final_svg)
        if svg_match:
            final_svg = svg_match.group(0)

        # ضمان الـ Namespace
        if 'xmlns=' not in final_svg:
            final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        return jsonify({
            "response": final_svg,
            "meta": {
                "layout_id": layout['id'],
                "engine": "V18.5_Core_Architect",
                "model": "Gemini_2.0_Flash"
            }
        })

    except Exception as e:
        logger.error(f"Execution Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # تهيئة المكتبة قبل تشغيل السيرفر
    app.run(host='0.0.0.0', port=10000)
