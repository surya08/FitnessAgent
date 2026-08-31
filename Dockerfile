FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Listen on dynamic port provided by Render
ENV PORT=10000
CMD ["sh", "-c", "streamlit run frontend.py --server.port ${PORT} --server.address 0.0.0.0"]
