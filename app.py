import os
import json
from flask import Flask, request, jsonify
# استخدام مكتبة جوجل الحديثة 2026
from google import genai
from google.genai import types

app = Flask(__name__)

# 1. إعداد العميل
API_KEY = os.environ.get('GOOGLE_API_KEY')
client = genai.Client(api_key=API_KEY) if API_KEY else None

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
            
    # Fallback default
    return os.path.join(base_path, "print/flyers.json")

@app.route('/')
def home(): return "Almonjez Ultimate Engine is Live! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        if not client: return jsonify({"error": "API Key missing"}), 500
        
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        # 1. تحديد مسار الملف
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        recipe_data = {} # القيمة الافتراضية
        
        # 2. قراءة الملف بحذر شديد (Critical Fix for List vs Dict)
        if os.path.exists(recipe_path):
            try:
                with open(recipe_path, 'r', encoding='utf-8') as f:
                    raw_content = json.load(f)
                    
                    # 🛡️ الفحص الأمني: هل هو قائمة أم قاموس؟
                    if isinstance(raw_content, list):
                        # إذا كان قائمة، نأخذ العنصر الأول
                        if len(raw_content) > 0:
                            recipe_data = raw_content[0]
                            print(f"ℹ️ Loaded first recipe from list: {recipe_path}")
                        else:
                            print(f"⚠️ Warning: Recipe list is empty in {recipe_path}")
                    elif isinstance(raw_content, dict):
                        # إذا كان قاموساً، نستخدمه كما هو
                        recipe_data = raw_content
                    else:
                        print(f"⚠️ Warning: Unknown JSON format in {recipe_path}")
                        
            except Exception as e:
                print(f"⚠️ Error parsing JSON file: {e}")
                # نستمر بقاموس فارغ لتجنب توقف السيرفر
                recipe_data = {}

        # الآن recipe_data هو قاموس { } بالتأكيد، ولن يحدث خطأ .get()
        
        # استخراج الأبعاد بأمان
        # نستخدم canvas_size الموجود في الوصفة، أو نستخدم الأبعاد المرسلة من التطبيق كبديل
        canvas_info = recipe_data.get('canvas_size', {})
        view_box = canvas_info.get('viewBox', f'0 0 {width} {height}')

        # 🧠 التعليمات المدمجة
        sys_instructions = f"""
        Role: You are 'Almonjez Master Architect'.
        Task: Create a print-ready SVG based on the User Request and the Master Blueprint (JSON).
        
        PHASE 1: GEOMETRY & LAYOUT (The Blueprint)
        - STRICTLY follow the 'layout_geometry', 'panels', and 'dimensions' from the JSON.
        - Draw the background shapes FIRST using <rect> or <path>.
        - Apply the colors defined in 'visual_style' (gradients, solid fills).
        - Use the specific paths provided in the JSON for headers/footers.
        
        PHASE 2: TYPOGRAPHY (The Content)
        - CRITICAL: NEVER use standard <text> tags for body text.
        - USE <foreignObject> for all text blocks to ensure Arabic wrapping.
        - Syntax:
          <foreignObject x=".." y=".." width=".." height="auto">
            <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right; font-family:sans-serif; color:black; word-wrap:break-word;">
              CONTENT_HERE
            </div>
          </foreignObject>
        
        PHASE 3: SPECS
        - ViewBox: {view_box}
        - Output: ONLY raw SVG code. No markdown.
        
        Blueprint Data: {json.dumps(recipe_data)}
        """

        # التوليد
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=sys_instructions,
                temperature=0.7
            )
        )

        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        print(f"✅ Generated Design: {len(svg_output)} bytes")
        return jsonify({"response": svg_output})

    except Exception as e:
        print(f"‼️ ERROR: {str(e)}")
        # إرجاع الخطأ بتفاصيل للمساعدة في التشخيص
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
