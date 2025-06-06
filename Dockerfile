# Mita Finance backend
FROM python:3.10-slim AS builder
WORKDIR /install
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.10-slim
WORKDIR /code
ENV PYTHONPATH=/code

COPY --from=builder /root/.local /usr/local
COPY . .

# Wait for Postgres before starting backend
COPY ./wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
