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

# ------------------------------------------------------
# 🔧 المسارات الحيوية على سيرفر Render (تم التصحيح)
# ------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPES_DIR = os.path.join(BASE_DIR, 'recipes')       # الدخول لمجلد الوصفات
CORE_PATH = os.path.join(RECIPES_DIR, 'core')         # استهداف مجلد core
PRINT_PATH = os.path.join(RECIPES_DIR, 'print')

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
    else:
        logger.warning("⚠️ GOOGLE_API_KEY Missing.")
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
        """قراءة الملفات الحقيقية من المجلدات المرفوعة مع التحقق من المسار"""
        try:
            layout_file = os.path.join(CORE_PATH, 'layout_sets.json')
            shape_file = os.path.join(CORE_PATH, 'shape_library.json')
            colors_file = os.path.join(CORE_PATH, 'colors.json')
            typo_file = os.path.join(CORE_PATH, 'typography.json')

            if os.path.exists(layout_file):
                with open(layout_file, 'r', encoding='utf-8') as f:
                    self.layouts = json.load(f)
            else:
                logger.error(f"❌ Missing File: {layout_file}")

            if os.path.exists(shape_file):
                with open(shape_file, 'r', encoding='utf-8') as f:
                    self.shapes = json.load(f)

            if os.path.exists(colors_file):
                with open(colors_file, 'r', encoding='utf-8') as f:
                    self.colors = json.load(f)

            if os.path.exists(typo_file):
                with open(typo_file, 'r', encoding='utf-8') as f:
                    self.typography = json.load(f)

            logger.info(f"📚 Library Synced: {len(self.layouts)} Layouts found.")
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
            
        # إضافة لون التمييز Accent إذا طلب في القالب
        accent_color = palette[-1] if palette else "#FF0000"
        svg_skeleton = svg_skeleton.replace("{{ACCENT}}", accent_color)
        
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
        
        if not GLOBAL_VAULT.layouts:
            return jsonify({"error": "Library layout_sets.json is empty or not found."}), 500
            
        # --- الخطوة 1: اختيار الوصفة والألوان (المنطق البشري المدفوع بالبايثون) ---
        layout = GLOBAL_VAULT.find_best_match(user_msg)
        palette = GLOBAL_VAULT.get_random_palette()
        params = GeometryResolver.resolve(layout)
        
        # بناء هيكل الطبقات الأساسي
        viewBox = layout['structure'].get('viewBox', '0 0 595 842')
        defs = "".join(layout['structure'].get('defs', []))
        
        layers_html = ""
        for layer in layout['structure'].get('layers', []):
            element_type = layer.get('element', 'path') # يدعم المسار كافتراضي
            
            fill = layer.get('fill', '#000')
            opacity = layer.get('opacity', 1.0)
            
            if element_type == 'path':
                d = layer.get('d_base', '')
                stroke = layer.get('stroke', '')
                stroke_width = layer.get('stroke_width', '')
                dash = layer.get('stroke_dasharray', '')
                
                path_str = f'<path d="{d}" fill="{fill}" opacity="{opacity}"'
                if stroke: path_str += f' stroke="{stroke}" stroke-width="{stroke_width}" stroke-dasharray="{dash}"'
                path_str += ' />\n'
                layers_html += path_str
                
            elif element_type == 'circle': # يدعم رسم الدوائر مثل قالب letterhead_official
                cx = layer.get('cx', '0')
                cy = layer.get('cy', '0')
                r = layer.get('r', '0')
                layers_html += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" opacity="{opacity}" />\n'

        # الهيكل الهيكلي الخام (نترك تعليقاً لجميني ليعرف أين يضع محتواه)
        skeleton = f'<svg viewBox="{viewBox}"><defs>{defs}</defs>{layers_html}</svg>'
        
        # معالجة الهيكل (حقن القيم)
        processed_skeleton = GeometryResolver.inject_assets(skeleton, params, palette)
        
        # --- الخطوة 2: التوجيه الإبداعي لـ Flash 2.0 ---
        safe_area = layout.get('logic', {}).get('text_safe_area', {})
        
        system_instruction = f"""
        ROLE: Senior Typographer (Almonjez Pro System).
        MODEL: Gemini 2.0 Flash (Execution Mode).

        === 🏛️ ARCHITECTURAL FRAMEWORK (FIXED) ===
        I have already resolved the professional geometry for '{layout.get('id', 'layout')}'.
        DO NOT alter the background paths or circles. You are responsible for the CONTENT LAYER.
        Place your text and foreground elements where `` is located in the SVG.

        === 📐 DESIGN CONSTRAINTS (HIERARCHY & CONTRAST) ===
        1. Safe Area: Top={safe_area.get('top', 50)}px, Bottom={safe_area.get('bottom', 50)}px, Left/Right={safe_area.get('left', 40)}px.
        2. Hierarchy: Title must be massive and contrast perfectly with background colors.
        3. Alignment: For Arabic text, use `direction="rtl"` and `text-anchor="end"`.
        4. Typography: Use fonts from the library: {json.dumps(GLOBAL_VAULT.typography.get('rtl_default', ['Arial']))}.

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
                "layout_id": layout.get('id', 'fallback'),
                "engine": "V18.5_Core_Architect",
                "model": "Gemini_2.0_Flash"
            }
        })

    except Exception as e:
        logger.error(f"Execution Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
