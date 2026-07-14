FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 10000
CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "10000"]
