import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. إعداد مفتاح API (يستخدم المفتاح القديم GOOGLE_API_KEY)
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel('gemini-1.5-pro-latest')

# 2. وظيفة ذكية لقراءة المكتبة الجديدة من المجلدات
def get_library_context():
    context = ""
    base_path = "recipes"
    if os.path.exists(base_path):
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if file.endswith(".json"):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # نأخذ فقط اسم القالب وأبعاده لتوفير المساحة في البرومبت
                            context += f"\nTemplate: {file}, Size: {data.get('canvas_size', 'standard')}"
                    except: continue
    return context

@app.route('/')
def index():
    return "Almonjez Engine is Online! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        # استقبال البيانات من كود Swift (OpenAIArchitect)
        user_message = data.get('message', '')
        template_from_app = data.get('template_data', '')

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # بناء السياق الاحترافي
        library_info = get_library_context()
        
        system_instruction = f"""
        You are the 'Almonjez Design Engine'. 
        Generate ONLY clean SVG code.
        
        AVAILABLE LIBRARY TEMPLATES (Reference for sizes):
        {library_info}
        
        GEOMETRY FROM APP:
        {template_from_app}
        
        IMPORTANT RULES:
        1. Use <text> with 'direction: rtl' and 'text-anchor: end' for Arabic.
        2. Ensure the viewBox matches the requested document type.
        3. For Trifold Brochures, use 3 columns layout.
        """

        full_prompt = f"{system_instruction}\n\nUser Request: {user_message}"
        response = model.generate_content(full_prompt)

        # الرد بالتنسيق الذي يتوقعه كود Swift
        return jsonify({
            "response": response.text
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
