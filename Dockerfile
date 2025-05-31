# Mita Finance backend
FROM python:3.10-slim

WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/code

# Wait for Postgres before starting backend
COPY ./wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]