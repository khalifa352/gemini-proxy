import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. إعداد الاتصال بـ Gemini (استخدام المفتاح المعرف في Render)
API_KEY = os.environ.get('GOOGLE_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

# استخدام موديل 2026 المستقر والأسرع
model = genai.GenerativeModel("gemini-2.0-flash")

# 2. نظام البحث المتساهل (Lenient Search) عن الوصفات
def get_recipe_lenient(category_name, user_prompt):
    base_path = "recipes"
    # تحويل النصوص لصغيرة لضمان المطابقة
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()
    
    # خريطة الربط المرنة بين الكلمات والمجلدات
    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json",
        "print": "print/flyers.json",
        "brochure": "print/brochures.json",
        "depliant": "print/brochures.json",
        "banner": "print/signage.json",
        "rollup": "print/signage.json",
        "menu": "print/menus.json",
        "social": "core/layout_sets.json",
        "post": "core/layout_sets.json",
        "invoice": "print/invoices.json",
        "فاتورة": "print/invoices.json",
        "كارت": "print/business_cards.json",
        "منيو": "print/menus.json",
        "مطوية": "print/brochures.json"
    }
    
    selected_path = None

    # البحث أولاً في التصنيف المختار من الواجهة
    for key, rel_path in flexible_map.items():
        if key in cat:
            selected_path = os.path.join(base_path, rel_path)
            break

    # إذا لم يجد، يبحث في نص "الطلب" نفسه
    if not selected_path:
        for key, rel_path in flexible_map.items():
            if key in prompt:
                selected_path = os.path.join(base_path, rel_path)
                break
                
    # الحل الأخير (Fallback): إذا لم يجد أي شيء، استخدم قالب الفلاير كقالب عام
    if not selected_path or not os.path.exists(selected_path):
        selected_path = os.path.join(base_path, "print/flyers.json")
        
    return selected_path

@app.route('/')
def index():
    return "Almonjez Design Engine is Live & Online! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width = data.get('width', 800)
        height = data.get('height', 600)
        
        # 🎯 سحب الوصفة المناسبة من مكتبة GitHub
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        
        recipe_data = {}
        if os.path.exists(recipe_path):
            with open(recipe_path, 'r', encoding='utf-8') as f:
                recipe_data = json.load(f)
        
        # بناء تعليمات النظام الصارمة لضمان جودة الـ SVG
        system_instruction = f"""
        Context: You are the 'Almonjez Design Engine'. 
        You must generate a professional SVG design based on the provided geometry.
        
        GEOMETRY RECIPE:
        {json.dumps(recipe_data)}
        
        CANVAS SIZE:
        Width: {width}, Height: {height}
        
        USER REQUEST:
        {user_msg}
        
        CRITICAL RULES:
        1. Output ONLY pure SVG code starting with <svg> and ending with </svg>.
        2. No explanations, no markdown (```), no preamble.
        3. For Arabic text: use <text> tags with 'direction: rtl' and 'text-anchor: end'.
        4. Colors must be professional and high-contrast.
        """
        
        # إرسال الطلب لـ Gemini
        response = model.generate_content(system_instruction)

        if response.text:
            # تنظيف أي علامات تنسيق زائدة من الرد
            clean_svg = response.text.replace("```svg", "").replace("```", "").strip()
            return jsonify({"response": clean_svg})
        else:
            return jsonify({"error": "Empty response from AI"}), 500

    except Exception as e:
        print(f"‼️ CRITICAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # تشغيل السيرفر على البورت المخصص لـ Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
