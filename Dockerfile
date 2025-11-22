FROM python:3.13-alpine

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY monitor_wan1.py .

# Create state directory
RUN mkdir -p /app && chmod 777 /app

CMD ["python", "-u", "monitor_wan1.py"]
