FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY assets /app/assets

RUN mkdir -p /app/assets/fonts \
  && curl -L -o /app/assets/fonts/ipaexg.ttf \
    https://github.com/ipa-fonts/ipaexfont/raw/master/ipaexg.ttf

ENV TEMPLATE_PDF_PATH=/app/assets/templates/sample-template.pdf \
    JAPANESE_FONT_PATH=/app/assets/fonts/ipaexg.ttf

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
