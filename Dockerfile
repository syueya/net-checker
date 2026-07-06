FROM python:3.12-alpine

RUN apk add --no-cache ca-certificates curl \
    && update-ca-certificates

WORKDIR /app
COPY app.py /app/app.py
COPY net_checker /app/net_checker
COPY static /app/static

ENV HOST=0.0.0.0 \
    PORT=8080 \
    CONFIG_PATH=/data/config.json

EXPOSE 8080
CMD ["python", "/app/app.py"]
