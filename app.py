import os
import json
import logging
import random
import re
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ CONFIGURATION & SYSTEM SETUP (ALMONJEZ V20)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Blueprint_Engine")

app = Flask(__name__)

# ======================================================
# 🔌 AI CLIENT (GEMINI 2.0 FLASH - FAST & SMART)
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ V20 Engine Connected (Gemini 2.0 Flash).")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY Missing.")
except Exception as e:
    logger.error(f"❌ AI Init Error: {e}")

# ======================================================
# 🧹 1. THE SANITIZER LAYER (حماية الـ JSON)
# ======================================================
class Sanitizer:
    @staticmethod
    def parse_json(raw_text):
        """استخراج وتعقيم JSON من أي مخرج عشوائي لجيميني"""
        try:
            # 1. البحث عن أول { وآخر }
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not match: return None
            
            json_str = match.group(0)
            
            # 2. إزالة الفواصل الزائدة (Trailing commas) التي تكسر الـ Parser
            json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Sanitizer Failed: {e}")
            return None

# ======================================================
# 🔤 2. THE TEXT ENGINE (محرك النصوص الصارم لـ iOS)
# ======================================================
class TextEngine:
    @staticmethod
    def build_foreign_object(x, y, w, h, text, font_size, max_lines, color, weight="normal"):
        """
        توليد صندوق نصي آمن (ForeignObject) مع CSS Clamping.
        مستحيل أن يخرج النص عن الـ Box أو يتمدد، مما يحمي الـ Layout تماماً.
        """
        # الهروب من الأقواس المعقوفة في f-string
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
# 📐 3. THE GEOMETRY ENGINE (محرك المخططات - Blueprint)
# ======================================================
class GeometryEngine:
    @staticmethod
    def get_blueprint(mode, w, h, seed):
        """
        توليد المخطط الهندسي: يحتوي على الأشكال الجاهزة + مناطق النصوص الدقيقة (Text Zones)
        """
        rnd = random.Random(seed)
        blueprint = {
            "viewBox": f"0 0 {w} {h}",
            "paths": [],
            "text_zones": {}
        }
        
        safe_margin = int(w * 0.08) # 8% margin
        
        if mode == "CURVE":
            # انحناءات طبية/ناعمة (Bottom Anchored)
            amp = int(h * rnd.uniform(0.12, 0.22))
            c1_y = h - int(amp * 1.6)
            
            p_back = f"M0,{h} L0,{h*0.4} C{w*0.3},{h*0.3} {w*0.7},{h*0.6} {w},{h*0.5} L{w},{h} Z"
            p_front = f"M0,{h} L0,{h*0.6} C{w*0.4},{h*0.5} {w*0.6},{h*0.8} {w},{h*0.7} L{w},{h} Z"
            
            blueprint["paths"] = [
                {"d": p_back, "fill": "{{PRIMARY}}", "opacity": 0.15},
                {"d": p_front, "fill": "{{PRIMARY}}", "opacity": 1.0}
            ]
            
            # Text Zones (أعلى الكيرف)
            blueprint["text_zones"] = {
                "title": {"x": safe_margin, "y": safe_margin, "w": w - (safe_margin*2), "h": int(h*0.15), "size": int(w*0.08), "lines": 2, "weight": "bold", "color": "{{PRIMARY}}"},
                "body":  {"x": safe_margin, "y": safe_margin + int(h*0.16), "w": w - (safe_margin*2), "h": int(h*0.25), "size": int(w*0.04), "lines": 5, "weight": "normal", "color": "#333333"}
            }
            
        else:
            # مضلعات حادة/رسمية (Corporate Sharp)
            peak = int(h * 0.25)
            p_header = f"M0,0 L{w},0 L{w},{peak} L0,{peak-50} Z"
            p_footer = f"M0,{h} L0,{h-80} L{w},{h-peak} L{w},{h} Z"
            
            blueprint["paths"] = [
                {"d": p_header, "fill": "{{PRIMARY}}", "opacity": 1.0},
                {"d": p_footer, "fill": "{{ACCENT}}", "opacity": 1.0}
            ]
            
            # Text Zones (في المساحة البيضاء بالمنتصف)
            blueprint["text_zones"] = {
                "title": {"x": safe_margin, "y": peak + 40, "w": w - (safe_margin*2), "h": int(h*0.12), "size": int(w*0.07), "lines": 2, "weight": "bold", "color": "{{PRIMARY}}"},
                "body":  {"x": safe_margin, "y": peak + 40 + int(h*0.14), "w": w - (safe_margin*2), "h": int(h*0.3), "size": int(w*0.035), "lines": 6, "weight": "normal", "color": "#111111"}
            }

        return blueprint

# ======================================================
# 🚀 4. THE PRODUCTION ROUTE (التجميع النهائي)
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V20 Blueprint Engine is Online 🍏"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        # 1. تحديد النمط الهندسي برمجياً (Python Logic)
        msg_lower = user_msg.lower()
        mode = "CURVE" if any(w in msg_lower for w in ['طبي', 'تجميل', 'ناعم', 'منحنى', 'medical']) else "SHARP"
        seed = random.randint(1000, 9999)
        
        # 2. توليد المخطط (The Blueprint)
        blueprint = GeometryEngine.get_blueprint(mode, width, height, seed)
        
        # 3. توجيه جيميني لكتابة الـ JSON فقط (بدون أي SVG)
        system_instruction = f"""
        ROLE: Expert Arabic Copywriter & Color Strategist.
        TASK: Extract intent from the user request and return strictly a JSON object.
        
        === 📏 TEXT BUDGET (STRICT CONTRACT) ===
        - "title": Max {blueprint['text_zones']['title']['lines'] * 4} words. Punchy and attractive.
        - "body": Max {blueprint['text_zones']['body']['lines'] * 8} words. Professional details.
        
        === 🎨 PALETTE ===
        - "primary": A hex color code suitable for the theme (e.g., #1A237E).
        - "accent": A complementary hex color code (e.g., #FF5252).
        
        === ✅ OUTPUT FORMAT ===
        Return ONLY valid JSON matching this schema exactly. No markdown, no conversation:
        {{
            "primary": "#HEX",
            "accent": "#HEX",
            "title": "العنوان هنا",
            "body": "التفاصيل هنا..."
        }}
        """

        # 4. استدعاء جيميني (سريع جداً لأنه يولد نصوصاً فقط)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4 # درجة حرارة منخفضة لضمان هيكل الـ JSON
            )
        )
        
        # 5. التعقيم والتحليل (Sanitize & Parse)
        ai_data = Sanitizer.parse_json(response.text)
        if not ai_data:
            return jsonify({"error": "Failed to parse AI Design Contract."}), 500
            
        # 6. التجميع الهندسي (SVG Assembly بواسطة Python)
        # أ. تجميع الأشكال الجاهزة
        paths_svg = ""
        for path in blueprint["paths"]:
            d = path["d"]
            fill = path["fill"].replace("{{PRIMARY}}", ai_data.get("primary", "#333")).replace("{{ACCENT}}", ai_data.get("accent", "#666"))
            opacity = path["opacity"]
            paths_svg += f'<path d="{d}" fill="{fill}" opacity="{opacity}" />\n'
            
        # ب. تجميع صناديق النصوص
        texts_svg = ""
        tz_title = blueprint["text_zones"]["title"]
        texts_svg += TextEngine.build_foreign_object(
            x=tz_title["x"], y=tz_title["y"], w=tz_title["w"], h=tz_title["h"],
            text=ai_data.get("title", "بدون عنوان"),
            font_size=tz_title["size"], max_lines=tz_title["lines"],
            color=tz_title["color"].replace("{{PRIMARY}}", ai_data.get("primary", "#000")),
            weight=tz_title["weight"]
        )
        
        tz_body = blueprint["text_zones"]["body"]
        texts_svg += TextEngine.build_foreign_object(
            x=tz_body["x"], y=tz_body["y"], w=tz_body["w"], h=tz_body["h"],
            text=ai_data.get("body", "لا توجد تفاصيل"),
            font_size=tz_body["size"], max_lines=tz_body["lines"],
            color=tz_body["color"], weight=tz_body["weight"]
        )
        
        # ج. إصدار الكود النهائي
        # حقن namespaces الأساسية لدعم iOS
        final_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xhtml="http://www.w3.org/1999/xhtml" viewBox="{blueprint['viewBox']}" width="100%" height="100%">
            {paths_svg}
            {texts_svg}
        </svg>"""

        # تنظيف نهائي للـ Whitespaces لتقليل حجم الـ Payload
        final_svg = re.sub(r'>\s+<', '><', final_svg.strip())

        return jsonify({
            "response": final_svg,
            "meta": {
                "engine": "V20_Deterministic_Blueprint",
                "mode": mode,
                "ai_contract": ai_data
            }
        })

    except Exception as e:
        logger.error(f"Assembly Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
