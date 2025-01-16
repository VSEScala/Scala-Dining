FROM python:3.13
LABEL org.opencontainers.image.source=https://github.com/VSEScala/Scala-Dining

ENV PYTHONUNBUFFERED=1

WORKDIR /app/src

COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --root-user-action ignore -r requirements.txt
COPY . .

# Collect static files
# TODO: Use a dedicated image for this and get rid of Whitenoise
ENV DINING_STATIC_ROOT=/app/static DINING_MEDIA_ROOT=/app/media DINING_SECRET_KEY='tmp'
RUN mkdir /app/media && python manage.py collectstatic --noinput
ENV DINING_SECRET_KEY=''

# Make commit hash available inside container
ARG COMMIT_SHA
ENV COMMIT_SHA=$COMMIT_SHA

CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "scaladining.wsgi"]
