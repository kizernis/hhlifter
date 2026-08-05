# Берем образ от Microsoft, в нем уже есть ВСЕ зависимости для браузеров
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Указываем, что установка должна быть неинтерактивной
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Moscow
RUN apt-get update && apt-get install -y tzdata && \
    ln -fs /usr/share/zoneinfo/Europe/Moscow /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir patchright==1.56

RUN patchright install chrome

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .