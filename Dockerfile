FROM python:3.10-slim

WORKDIR usr/src/app

# ODBC sürücüleri ve bağımlılıkları kur
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
