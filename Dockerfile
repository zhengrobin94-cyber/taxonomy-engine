FROM python:3.12

WORKDIR /taxonomy-engine

# Install system dependencies
# NOTE: none needed

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Enable cross-module imports
ENV PYTHONPATH="/taxonomy-engine"

CMD ["python", "app/api/main.py"]