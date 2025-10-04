FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN ls

RUN addgroup -g 10016 choreo \
    && adduser --disabled-password --no-create-home --uid 10016 --ingroup choreo choreouser
USER 10016

EXPOSE 8003

CMD ["uvicorn", "evidence_agent:app", "--host=0.0.0.0", "--port=8003"]
