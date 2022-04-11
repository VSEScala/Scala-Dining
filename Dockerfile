FROM python:3.8

# Python settings
ENV PYTHONUNBUFFERED=1

WORKDIR /app/src

# Install dependencies
COPY requirements requirements
RUN pip install --no-cache-dir -r requirements/common.txt -r requirements/prod.txt

COPY . .

# Collect static files
ENV DINING_STATIC_ROOT=/app/static DINING_MEDIA_ROOT=/app/media DINING_SECRET_KEY='tmp'
RUN mkdir /app/media && python manage.py collectstatic --noinput
ENV DINING_SECRET_KEY=''

# Make commit hash and build date available inside container
ARG COMMIT_SHA
ARG BUILD_TIMESTAMP
ENV COMMIT_SHA=$COMMIT_SHA
ENV BUILD_TIMESTAMP=$BUILD_TIMESTAMP

# Create user
RUN useradd -u 1001 appuser && chown appuser /app/media
USER appuser

# By default launch gunicorn on :8000
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "scaladining.wsgi"]
