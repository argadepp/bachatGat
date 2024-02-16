FROM python:3.8

WORKDIR /app

COPY requirements.txt /app/requirements.txt

COPY . .

RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["python", "app.py"]