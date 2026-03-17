# استخدام نسخة بايثون خفيفة كبيئة أساسية
FROM python:3.10-slim

# منع بايثون من كتابة ملفات التخزين المؤقت وتوجيه السجلات مباشرة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# تحديث النظام وتثبيت LibreOffice وخطوط بديلة لـ Arial مع دعم عربي أساسي ومضمون
RUN apt-get update && apt-get install -y \
    libreoffice \
    fonts-liberation \
    fonts-kacst \
    && rm -rf /var/lib/apt/lists/*

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تحديد البورت
EXPOSE 10000

# أمر التشغيل
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "120"]
