FROM python:3.8-buster

# Python settings
ENV PYTHONUNBUFFERED=1

WORKDIR /app/src

# Install dependencies
RUN pip install --no-cache-dir gunicorn psycopg2
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files
ENV DINING_STATIC_ROOT=/app/static DINING_MEDIA_ROOT=/app/media DINING_SECRET_KEY='tmp'
RUN mkdir /app/media && python manage.py collectstatic --noinput
ENV DINING_SECRET_KEY=''

# Create user
RUN useradd -u 1001 appuser && chown appuser /app/media
USER appuser

# By default launch gunicorn on :8000
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "ScalaApp.wsgi"]
