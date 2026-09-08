FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py database.py google_auth.py validation.py seed.py schema.sql serve_online.py ./
COPY templates ./templates
COPY static ./static
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
EXPOSE 8080
CMD ["python", "serve_online.py"]
