FROM python:3.11 AS base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /backend

# Installer les dépendances système (Alpine utilise apk)
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev

# Copier et installer les requirements
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copier le projet
COPY . .

# Créer le dossier pour la base de données
# RUN mkdir -p /backend/db

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]