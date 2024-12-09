FROM python:3.9-slim

WORKDIR /app

# Создаем директорию для данных и устанавливаем права
RUN mkdir -p /data && \
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