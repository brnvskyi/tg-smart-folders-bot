FROM python:3.9-slim

WORKDIR /app

# Создаем директории для данных и логов с нужными правами
RUN mkdir -p /data/logs && \
    mkdir -p /data/user_data && \
    chmod -R 777 /data && \
    chown -R nobody:nogroup /data

# Копируем и устанавливаем зависимости как root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Переключаемся на непривилегированного пользователя
USER nobody

# Устанавливаем переменную окружения для пути к данным
ENV DATA_DIR=/data

# Копируем код приложения с правильными правами
COPY --chown=nobody:nogroup . .

CMD ["python", "bot.py"] 