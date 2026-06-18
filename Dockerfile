FROM python:3.10-slim

WORKDIR /app

# Memasang fail keperluan sistem asas
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Menyalin keseluruhan kod aplikasi anda
COPY . .

# Memasang pakej-pakej Python daripada requirements.txt anda
RUN pip3 install --no-cache-dir -r requirements.txt

# Mendedahkan port 7860 yang diwajibkan oleh Hugging Face Spaces
EXPOSE 7860

# Menjalankan fail utama aplikasi anda dengan menutup sekatan CORS/XSRF Hugging Face
CMD ["streamlit", "run", "main.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
