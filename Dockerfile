FROM python:3.9-slim

WORKDIR /app

# Создаем директорию для данных
RUN mkdir -p /data/user_data && chmod 777 /data/user_data

# Устанавливаем переменную окружения для пути к данным
ENV DATA_DIR=/data/user_data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"] 