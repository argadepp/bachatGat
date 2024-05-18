FROM python:3.8

WORKDIR /app
ENV DB_HOST=localhost
ENV DB_USER=username
ENV DB_PASSWORD=password
ENV DB_NAME=database_name


COPY . .
RUN pip install prettytable
RUN pip install python-dateutil

RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["python", "app.py"]