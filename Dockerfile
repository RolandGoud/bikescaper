FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BIKECOMPARE_DB=/data/bikecompare.sqlite3

WORKDIR /app
COPY webapp/requirements.txt webapp/requirements.txt
RUN pip install --no-cache-dir -r webapp/requirements.txt

# The site needs the app, the scraped JSON it seeds from, and the bike photos.
COPY webapp webapp
COPY data data
COPY images images

VOLUME /data
EXPOSE 8000

# Load the catalogue on first start only, so saved checks and corrected matches survive restarts.
CMD ["sh", "-c", "python -m webapp.seed --if-empty && exec gunicorn --bind 0.0.0.0:8000 --workers 2 --access-logfile - webapp.app:app"]
