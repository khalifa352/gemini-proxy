# استخدام نسخة بايثون ونظام (Bookworm) المستقرة
FROM python:3.10-slim-bookworm

# منع بايثون من كتابة ملفات التخزين المؤقت وتوجيه السجلات مباشرة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# تفعيل مستودعات contrib و non-free لتحميل خط Arial الأصلي من مايكروسوفت
RUN sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources || true

# الموافقة التلقائية على اتفاقية استخدام خطوط مايكروسوفت
RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections

# تثبيت Xvfb (الشاشة الوهمية)، LibreOffice، خط Arial، وأدوات التحميل
RUN apt-get update && apt-get install -y \
    wget \
    cabextract \
    xvfb \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    default-jre \
    ttf-mscorefonts-installer \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# تحديث كاش الخطوط في السيرفر ليتعرف LibreOffice على خط Arial كخط أساسي
RUN fc-cache -f -v

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تحديد البورت
EXPOSE 10000

# 🌟 السحر هنا: تشغيل الشاشة الوهمية (:99) في الخلفية أولاً، ثم تشغيل سيرفر بايثون
# هذا سيلبي طلب app.py ويمنع خطأ (Can't open display) دون المساس بالكود البرمجي!
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x24 & gunicorn app:app --bind 0.0.0.0:10000 --timeout 120"]

