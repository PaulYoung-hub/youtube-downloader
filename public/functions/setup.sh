#!/bin/bash

# Télécharger yt-dlp
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp

# Rendre le fichier exécutable
chmod +x yt-dlp

# Créer le dossier bin s'il n'existe pas
mkdir -p bin

# Déplacer yt-dlp dans le dossier bin
mv yt-dlp bin/

# Vérifier l'installation
./bin/yt-dlp --version
