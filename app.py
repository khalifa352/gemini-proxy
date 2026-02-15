import os
import json
import logging
import random
from flask import Flask, request, jsonify

# 1. إعداد السجلات (Logs)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 2. اتصال آمن بالمكتبة (Google GenAI 2026)
client = None
try:
    from google import genai
    from google.genai import types
    
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        logger.info("✅ Google GenAI Client Connected (Generative Mode)")
    else:
        logger.warning("⚠️ Warning: API Key missing")
except ImportError:
    logger.error("❌ Library 'google-genai' not found. Please update requirements.txt")
except Exception as e:
    logger.error(f"❌ Client Init Error: {e}")

# 3. دالة جلب "أنظمة التصميم" (Design Systems Catalog)
def get_design_rules(category_name, user_prompt):
    """
    بدلاً من جلب وصفة واحدة، نجلب كتالوجاً من "القواعد التوليدية".
    """
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()
    
    # خريطة المجلدات
    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json",
        "brochure": "print/brochures.json",
        "menu": "print/menus.json",
        "invoice": "print/invoices.json",
        "certificate": "print/certificates.json"
    }
    
    # المسار الافتراضي
    selected_path = os.path.join(base_path, "print/flyers.json")
    
    # البحث الذكي
    for key, path in flexible_map.items():
        if key in cat or key in prompt:
            full_path = os.path.join(base_path, path)
            if os.path.exists(full_path):
                selected_path = full_path
                break
    
    # قراءة الملف وإرجاع القائمة كاملة
    try:
        with open(selected_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            if isinstance(raw, list): return raw
            if isinstance(raw, dict): return [raw]
    except Exception as e:
        logger.error(f"⚠️ Error reading rules: {e}")
        return [] # نرجع قائمة فارغة في حال الخطأ ليستخدم ذكاءه العام

# 4. المسار الرئيسي (Health Check)
@app.route('/')
def home():
    return "Almonjez Generative Engine is Active 🧠🎨"

# 5. مسار التوليد (The Brain)
@app.route('/gemini', methods=['POST'])
def generate():
    if not client: 
        return jsonify({"error": "Server Error: AI Client not ready"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        logger.info(f"📥 Generating for: {cat_name} | Canvas: {width}x{height}")

        # أ. جلب قواعد التصميم المتاحة
        available_rules = get_design_rules(cat_name, user_msg)
        
        # ب. تعليمات "المهندس المولد" (The Generative Architect Prompt)
        sys_instructions = f"""
        Role: World-Class Generative SVG Artist & Mathematician.
        Mission: Generate a UNIQUE, Professional SVG design. Do NOT use fixed templates.
        
        INPUT DATA:
        - User Request: "{user_msg}"
        - Canvas Size: {width}x{height} (ViewBox: 0 0 {width} {height})
        - Design Systems Available: {json.dumps(available_rules)}
        
        PHASE 1: SELECTION & ANALYSIS
        - Analyze the user's text volume and industry (e.g., Medical, Food, Tech).
        - Select the most suitable "Design System" from the provided JSON list.
        - If the system defines 'generative_rules', you MUST follow them but vary the parameters.
        
        PHASE 2: GEOMETRY CALCULATION (The "Fishing" Part)
        - Do NOT just copy-paste paths. CALCULATE them.
        - If a rule says "header_curve: random height 100-300", pick a specific number (e.g., 245) and draw a Bezier curve (Q or C command) utilizing that height.
        - Create fluid, organic, or geometric shapes based on the industry style.
        - RULE: Must cover the entire background (Full Bleed). No white margins.
        
        PHASE 3: COLOR PSYCHOLOGY
        - Detect the brand mood from the text.
        - Generate professional <linearGradient> or <radialGradient> definitions in <defs>.
        - Apply these gradients to your generated shapes.
        - Ensure High Contrast for text (White text on Dark BG, Dark text on Light BG).
        
        PHASE 4: TYPOGRAPHY (HTML Engine)
        - ALWAYS use <foreignObject> for text support (Arabic/English).
        - Scale font-size dynamically:
          * Short text -> Large, Bold, Impactful.
          * Long text -> Smaller, Organized, Grid-based.
        - Syntax:
          <foreignObject x=".." y=".." width=".." height="auto">
             <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right; font-family:sans-serif; color:CONTRAST_COLOR;">
                CONTENT
             </div>
          </foreignObject>
        
        OUTPUT:
        - Return ONLY the raw SVG code.
        - Start with <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">.
        """

        # ج. الطلب من Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=sys_instructions,
                temperature=0.8  # رفعنا درجة الإبداع ليعطي نتائج مختلفة كل مرة
            )
        )

        # د. تنظيف الرد
        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        
        # ضمان وجود xmlns (إصلاح مشاكل العرض في آيفون)
        if '<svg' in svg_output and 'xmlns=' not in svg_output:
            svg_output = svg_output.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
            
        return jsonify({"response": svg_output})

    except Exception as e:
        logger.error(f"‼️ Generation Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # استخدام المنفذ الديناميكي لـ Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
