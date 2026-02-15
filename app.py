from flask import Flask, request, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

# 1. إعداد مفتاح جيميني من متغيرات البيئة (أكثر أماناً)
# أو يمكنك وضعه هنا مؤقتاً للتجربة: genai.configure(api_key="YOUR_GEMINI_KEY")
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# إعداد الموديل
model = genai.GenerativeModel('gemini-1.5-pro-latest')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        
        # استقبال النص من تطبيقك (Swift)
        # تطبيقك يرسل { "prompt": "تصميم كذا وكذا..." }
        user_prompt = data.get('prompt', '')
        system_instruction = data.get('system', '')

        if not user_prompt:
            return jsonify({"error": "No prompt provided"}), 400

        # دمج تعليمات النظام مع طلب المستخدم (لأن جيميني يتعامل معها بشكل مختلف قليلاً)
        full_prompt = f"{system_instruction}\n\nUser Request: {user_prompt}"

        # إرسال الطلب لجوجل (السيرفر في أمريكا لذا سيعمل)
        response = model.generate_content(full_prompt)

        # إعادة النص فقط للتطبيق
        return jsonify({
            "choices": [
                {
                    "message": {
                        "content": response.text
                    }
                }
            ]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # تشغيل السيرفر
    app.run(host='0.0.0.0', port=10000)
