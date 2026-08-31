FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use PORT environment variable dynamically provided by Render
ENV PORT=10000
CMD ["sh", "-c", "streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0"]
