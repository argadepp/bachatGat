FROM python:3.9-slim

WORKDIR /app

COPY bachat_gat_web.py .
COPY templates/ ./templates/
COPY static/ ./static/
COPY translations/ ./translations/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pybabel compile -d translations

EXPOSE 5000

CMD ["python", "bachat_gat_web.py"]