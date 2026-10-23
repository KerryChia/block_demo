FROM python:3.11-slim
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ server/
COPY web/ web/
COPY run.py .
ENV DATA_DIR=/app/data PORT=8300
VOLUME /app/data
EXPOSE 8300
CMD ["python", "run.py"]
