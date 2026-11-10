FROM python:3.12-slim

WORKDIR /app
COPY history_api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY history_api ./history_api
RUN python -m history_api.seed && chmod 444 history_api/data/history.db && chmod 555 history_api/data

ENV HISTORY_DATABASE_URL=sqlite:///file:/app/history_api/data/history.db?mode=ro&uri=true
ENV PORT=8080
EXPOSE 8080
USER 10001

CMD ["sh", "-c", "uvicorn history_api.main:app --host 0.0.0.0 --port ${PORT}"]
