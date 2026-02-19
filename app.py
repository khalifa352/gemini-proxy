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
# 🔧 المسارات الحيوية على سيرفر Render
# ------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPES_DIR = os.path.join(BASE_DIR, 'recipes')       
CORE_PATH = os.path.join(RECIPES_DIR, 'core')         
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
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Gemini 2.0 Flash Engine Initialized.")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY Missing.")
except Exception as e:
    logger.error(f"❌ AI Init Error: {e}")

# ======================================================
# 📂 1. THE ASSET VAULT
# ======================================================
class AssetVault:
    def __init__(self):
        self.layouts = []
        self.shapes = []
        self.colors = []
        self.typography = {}
        self.refresh_library()

    def refresh_library(self):
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
        msg = user_msg.lower()
        candidates = [l for l in self.layouts if any(v in msg for v in l.get('vibes', []))]
        return random.choice(candidates if candidates else self.layouts) if self.layouts else {}

    def get_random_palette(self):
        return random.choice(self.colors) if self.colors else ["#000000", "#FFFFFF"]

GLOBAL_VAULT = AssetVault()

# ======================================================
# 📐 2. THE GEOMETRY RESOLVER
# ======================================================
class GeometryResolver:
    @staticmethod
    def resolve(layout_set):
        resolved = {}
        params = layout_set.get('params', {})
        for key, limits in params.items():
            resolved[key] = random.randint(limits['min'], limits['max'])
        return resolved

    @staticmethod
    def inject_assets(svg_skeleton, params, palette):
        for i, color in enumerate(palette, 1):
            svg_skeleton = svg_skeleton.replace(f"{{{{COLOR_{i}}}}}", color)
            
        accent_color = palette[-1] if palette else "#FF0000"
        svg_skeleton = svg_skeleton.replace("{{ACCENT}}", accent_color)
        
        for key, val in params.items():
            svg_skeleton = svg_skeleton.replace(f"{{{{{key}}}}}", str(val))
        
        return svg_skeleton

# ======================================================
# 🌐 3. HEALTH CHECK (لرؤية النتيجة فور فتح الرابط)
# ======================================================
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "Online 🎉",
        "engine": "Almonjez_V18.5_Core_Architect",
        "library_loaded": len(GLOBAL_VAULT.layouts) > 0,
        "message": "The server is running perfectly. Send a POST request to /gemini to generate SVG."
    })

# ======================================================
# 🚀 4. THE PRODUCTION ENGINE (POST ROUTE)
# ======================================================
@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Engine Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        
        if not GLOBAL_VAULT.layouts:
            return jsonify({"error": "Library layout_sets.json is empty or not found."}), 500
            
        layout = GLOBAL_VAULT.find_best_match(user_msg)
        palette = GLOBAL_VAULT.get_random_palette()
        params = GeometryResolver.resolve(layout)
        
        viewBox = layout.get('structure', {}).get('viewBox', '0 0 595 842')
        defs = "".join(layout.get('structure', {}).get('defs', []))
        
        layers_html = ""
        for layer in layout.get('structure', {}).get('layers', []):
            element_type = layer.get('element', 'path')
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
                
            elif element_type == 'circle':
                cx = layer.get('cx', '0')
                cy = layer.get('cy', '0')
                r = layer.get('r', '0')
                layers_html += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" opacity="{opacity}" />\n'

        skeleton = f'<svg viewBox="{viewBox}"><defs>{defs}</defs>{layers_html}</svg>'
        processed_skeleton = GeometryResolver.inject_assets(skeleton, params, palette)
        
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

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[f"User Request: {user_msg}\n\nProcessed Skeleton:\n{processed_skeleton}"],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4 
            )
        )
        
        final_svg = response.text
        svg_match = re.search(r"(?s)<svg[^>]*>.*?</svg>", final_svg)
        if svg_match:
            final_svg = svg_match.group(0)

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
    # تم تصحيح المنفذ ليتوافق مع Render ديناميكياً
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
