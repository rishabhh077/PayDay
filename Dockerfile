FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# The database lives in /data so it survives a new container: mount a volume there.
RUN useradd --create-home payday && mkdir /data && chown payday /data
USER payday
ENV PAYDAY_DB=/data/payday.db PAYDAY_SCHEDULER=1
VOLUME /data
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app:app"]
