import os
import json
import logging
import random # لاستخدام العشوائية عند عدم وجود تفضيل
from flask import Flask, request, jsonify

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- استيراد المكتبة ---
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

# --- 🧠 دالة الاختيار الذكي (The Smart Selector) ---
def pick_best_recipe(recipes_list, user_prompt):
    """
    تختار أفضل وصفة بناءً على طلب المستخدم.
    إذا طلب 'مودرن'، تختار الوصفة التي تحتوي على id='modern' وهكذا.
    """
    if not recipes_list: return {}
    
    prompt_lower = user_prompt.lower()
    best_recipe = None
    highest_score = -1
    
    logger.info(f"🔍 Scanning {len(recipes_list)} recipes for matches...")

    for recipe in recipes_list:
        score = 0
        # 1. فحص المعرف (ID)
        rec_id = recipe.get('id', '').lower()
        if rec_id in prompt_lower: score += 10
        
        # 2. فحص الوصف (Description)
        desc = recipe.get('description', '').lower()
        for word in prompt_lower.split():
            if word in desc or word in rec_id:
                score += 2
        
        # 3. فحص الكلمات المفتاحية (Tags/Keywords) إن وجدت
        tags = recipe.get('tags', [])
        for tag in tags:
            if tag.lower() in prompt_lower:
                score += 5

        logger.info(f"   - Recipe [{rec_id}] Score: {score}")

        if score > highest_score:
            highest_score = score
            best_recipe = recipe
    
    # إذا لم نجد أي تطابق (Score 0)، نختار عشوائياً للتنوع
    if highest_score <= 0:
        logger.info("🎲 No specific match found. Picking RANDOM recipe.")
        return random.choice(recipes_list)
    
    logger.info(f"🎯 Selected Best Match: {best_recipe.get('id')}")
    return best_recipe

# --- دالة جلب الملف ---
def get_recipe_path(category_name, user_prompt):
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
def home(): return "Almonjez Engine: Smart Selection Active 🧠"

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Server Error: Client failed"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        logger.info(f"📥 Request: {cat_name} | Prompt: {user_msg}")

        # 1. جلب ملف الوصفات
        recipe_path = get_recipe_path(cat_name, user_msg)
        selected_recipe = {}
        
        if os.path.exists(recipe_path):
            try:
                with open(recipe_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    
                    # 🚀 هنا التغيير الجذري: الاختيار الذكي بدلاً من الأول فقط
                    if isinstance(raw, list):
                        selected_recipe = pick_best_recipe(raw, user_msg)
                    elif isinstance(raw, dict):
                        selected_recipe = raw
            except Exception as e:
                logger.error(f"⚠️ JSON Error: {e}")

        # 2. تجهيز التعليمات
        view_box = selected_recipe.get('canvas_size', {}).get('viewBox', f'0 0 {width} {height}')

        sys_instructions = f"""
        Role: Senior Graphic Designer.
        Task: Create a 'Full Bleed' SVG design based on the Selected Blueprint.
        
        SELECTED BLUEPRINT ID: {selected_recipe.get('id', 'Unknown')}
        
        RULE 1: GEOMETRY
        - Use the specific 'layout_geometry' from the Blueprint.
        - If the blueprint has a specific background pattern, DRAW IT.
        - NO WHITE MARGINS. Fill the canvas.
        
        RULE 2: TEXT (HTML Engine)
        - ALWAYS use <foreignObject> for text.
        - Syntax:
          <foreignObject x=".." y=".." width=".." height="auto">
             <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right; font-family:sans-serif; color:CONTRAST_COLOR;">
                CONTENT
             </div>
          </foreignObject>
        
        Blueprint Data: {json.dumps(selected_recipe)}
        """

        # التوليد
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions)
        )

        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        if '<svg' in svg_output and 'xmlns=' not in svg_output:
            svg_output = svg_output.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
            
        return jsonify({"response": svg_output})

    except Exception as e:
        logger.error(f"‼️ Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
