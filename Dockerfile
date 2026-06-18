FROM python:3.10-slim

WORKDIR /app

# Memasang fail keperluan sistem (system dependencies) untuk pemprosesan fail geografi
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Menyalin keseluruhan kod aplikasi anda ke dalam kontena
COPY . .

# Memasang pakej-pakej python daripada requirements.txt anda
RUN pip3 install --no-cache-dir -r requirements.txt

# Mendedahkan port 7860 yang diwajibkan oleh pihak Hugging Face Spaces
EXPOSE 7860

# Arahan wajib untuk menjalankan Streamlit pada port Hugging Face
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
