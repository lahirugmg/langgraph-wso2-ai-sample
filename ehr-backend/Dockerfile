FROM python:alpine

WORKDIR /python-docker

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .
RUN ls

RUN addgroup -g 10016 choreo && \
    adduser --disabled-password --no-create-home --uid 10016 --ingroup choreo choreouser
USER 10016

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=8001"]
