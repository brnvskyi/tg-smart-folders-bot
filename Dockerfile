FROM python:3.9-slim

WORKDIR /app

# Создаем директорию для данных и устанавливаем права
RUN mkdir -p /data && chmod 777 /data

# Устанавливаем переменную окружения для пути к данным
ENV DATA_DIR=/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем директорию для пользовательских данных и устанавливаем права
RUN mkdir -p /data/user_data && chmod 777 /data/user_data

CMD ["python", "bot.py"] 