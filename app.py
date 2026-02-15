import os
import json
import logging
from flask import Flask, request, jsonify

# إعداد السجلات (Logs) لنرى الأخطاء بوضوح
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- منطقة الأمان: استيراد المكتبة بحذر ---
client = None
try:
    # محاولة استيراد مكتبة 2026
    from google import genai
    from google.genai import types
    
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        logger.info("✅ Google GenAI Client Connected Successfully")
    else:
        logger.warning("⚠️ Warning: GOOGLE_API_KEY not found in environment variables")
        
except ImportError as e:
    logger.error(f"❌ CRITICAL: Library 'google-genai' failed to import. Did you Clear Build Cache? Error: {e}")
except Exception as e:
    logger.error(f"❌ Startup Error: {e}")

# --- الوظائف المساعدة ---
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

# --- المسارات (Routes) ---

@app.route('/')
def health_check():
    # هذا المسار سيعمل حتى لو كانت المكتبة معطلة، مما يمنع خطأ "No Ports Detected"
    status = "Active" if client else "Inactive (Check Logs)"
    return f"Almonjez Engine Status: {status} 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    # فحص أخير قبل العمل
    if not client:
        return jsonify({"error": "Server is running, but AI Client failed to initialize. Check Render Logs."}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        logger.info(f"📥 Processing Request: {cat_name}")

        # 1. جلب الوصفة
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        recipe_data = {}
        
        # 2. قراءة الملف (مع حل مشكلة القوائم)
        if os.path.exists(recipe_path):
            try:
                with open(recipe_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        recipe_data = raw[0] if raw else {}
                    elif isinstance(raw, dict):
                        recipe_data = raw
            except Exception as e:
                logger.error(f"⚠️ JSON Read Error: {e}")

        # 3. التعليمات
        view_box = recipe_data.get('canvas_size', {}).get('viewBox', f'0 0 {width} {height}')
        
        sys_instructions = f"""
        Role: Master SVG Architect.
        Task: Generate print-ready SVG.
        
        1. GEOMETRY: Use the provided JSON to draw background shapes (<rect>, <path>).
        2. TEXT: ALWAYS use <foreignObject> for text. NO <text> tags.
        3. SYNTAX:
           <foreignObject x=".." y=".." width=".." height="auto">
             <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right; font-family:sans-serif; color:black; word-wrap:break-word;">
               CONTENT
             </div>
           </foreignObject>
        4. SPECS: ViewBox="{view_box}".
        
        Recipe: {json.dumps(recipe_data)}
        """

        # التوليد
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions)
        )

        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        return jsonify({"response": svg_output})

    except Exception as e:
        logger.error(f"‼️ Runtime Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
