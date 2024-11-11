FROM python:alpine3.17
WORKDIR /app
COPY . /app
RUN ls
#RUN pip install -r requirements
ENTRYPOINT ["python", "main.py"]