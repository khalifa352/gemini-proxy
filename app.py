import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. إعداد المفتاح (تأكد من وجوده في Render باسم GOOGLE_API_KEY)
API_KEY = os.environ.get('GOOGLE_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

# 2. إعداد الموديل مع إيقاف فلاتر الأمان لضمان توليد الكود دون حجب
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    ‏model = genai.GenerativeModel('gemini-2.0-flash') # استخدام النسخة المستقرة
    generation_config=generation_config,
    safety_settings=safety_settings
)

@app.route('/')
def index():
    return "Almonjez Engine is Online! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_message = data.get('message', '')
        template_from_app = data.get('template_data', '')

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # تبسيط تعليمات النظام
        system_instruction = """
        You are 'Almonjez Design Engine'. 
        Generate ONLY professional SVG code. 
        Use RTL for Arabic. 
        Do not explain anything, just output the code starting with <svg>.
        """

        full_prompt = f"{system_instruction}\n\nUser Prompt: {user_message}\nLayout Template: {template_from_app}"
        
        response = model.generate_content(full_prompt)

        if response.text:
            return jsonify({"response": response.text})
        else:
            return jsonify({"error": "Gemini returned empty response"}), 500

    except Exception as e:
        print(f"‼️ ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
