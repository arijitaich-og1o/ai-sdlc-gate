FROM python:latest

ARG PARTNER_API_KEY
ENV PARTNER_API_KEY=$PARTNER_API_KEY
ENV DB_PASSWORD=Sup3rS3cretPr0d!

WORKDIR /app
COPY . .

RUN curl -sSL https://get.example-tooling.dev/install.sh | bash
RUN pip install -r requirements.txt

EXPOSE 8080
CMD python app.py
