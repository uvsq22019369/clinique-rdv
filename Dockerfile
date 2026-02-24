# Utilise une image Python officielle et légère
FROM python:3.11-slim

# Définit le répertoire de travail dans le conteneur
WORKDIR /app

# Copie d'abord le fichier des dépendances (pour profiter du cache Docker)
COPY requirements.txt .

# Installe les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copie tout le reste du projet
COPY . .

# Expose le port sur lequel Render communique
EXPOSE 10000

# Commande pour démarrer l'application
CMD gunicorn run:app