from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import tempfile
from typing import Optional
import logging
import sys
import requests
import re
from urllib.parse import parse_qs, urlparse

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str
    type: str
    quality: Optional[str] = "720"

def get_video_id(url: str) -> str:
    """Extraire l'ID de la vidéo YouTube de l'URL."""
    if match := re.search(r'(?:v=|\/)([\w-]{11})', url):
        return match.group(1)
    parsed = urlparse(url)
    if parsed.path.startswith('/watch'):
        return parse_qs(parsed.query).get('v', [None])[0]
    return url

def download_with_ytdlp(url: str, output_path: str, type_: str, quality: str):
    """Télécharger avec yt-dlp avec une configuration optimisée."""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if type_ == 'video' else 'bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'noprogress': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
        }
    }

    if type_ == "audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    elif quality != "highest":
        ydl_opts['format'] = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            return True
        except Exception as e:
            logger.error(f"Erreur yt-dlp: {str(e)}")
            return False

def download_with_alternative(url: str, output_path: str, type_: str, quality: str):
    """Méthode alternative de téléchargement."""
    try:
        video_id = get_video_id(url)
        if not video_id:
            raise ValueError("ID de vidéo invalide")

        # Utiliser une API alternative pour obtenir les liens directs
        api_url = f"https://api.vevioz.com/@api/json/mp4/{video_id}"
        response = requests.get(api_url)
        if response.status_code != 200:
            raise Exception("Impossible d'obtenir les informations de la vidéo")

        data = response.json()
        if not data or 'links' not in data:
            raise Exception("Format de réponse invalide")

        # Choisir le meilleur lien selon la qualité demandée
        available_links = data['links']
        selected_link = None
        
        if type_ == "audio":
            for link in available_links:
                if link.get('type') == 'mp3':
                    selected_link = link.get('url')
                    break
        else:
            target_quality = int(quality) if quality != "highest" else 1080
            best_quality = 0
            for link in available_links:
                if link.get('type') == 'mp4':
                    q = int(link.get('quality', '0').replace('p', ''))
                    if q <= target_quality and q > best_quality:
                        best_quality = q
                        selected_link = link.get('url')

        if not selected_link:
            raise Exception("Aucun lien disponible pour la qualité demandée")

        # Télécharger le fichier
        response = requests.get(selected_link, stream=True)
        if response.status_code != 200:
            raise Exception("Erreur lors du téléchargement")

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return True

    except Exception as e:
        logger.error(f"Erreur alternative: {str(e)}")
        return False

@app.post("/api/download")
async def download_video(request: DownloadRequest):
    logger.info(f"Nouvelle requête de téléchargement: {request.dict()}")
    
    try:
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Définir le nom du fichier de sortie
            ext = "mp3" if request.type == "audio" else "mp4"
            output_path = os.path.join(temp_dir, f"video.{ext}")
            
            # Essayer d'abord avec yt-dlp
            success = download_with_ytdlp(request.url, output_path, request.type, request.quality)
            
            # Si yt-dlp échoue, essayer la méthode alternative
            if not success:
                logger.info("yt-dlp a échoué, essai de la méthode alternative")
                success = download_with_alternative(request.url, output_path, request.type, request.quality)

            if not success:
                raise HTTPException(
                    status_code=400,
                    detail="Impossible de télécharger la vidéo. Essayez une autre vidéo ou réessayez plus tard."
                )

            if not os.path.exists(output_path):
                raise HTTPException(status_code=404, detail="Le fichier n'a pas été créé")

            file_size = os.path.getsize(output_path)
            if file_size == 0:
                raise HTTPException(status_code=400, detail="Le fichier téléchargé est vide")

            def iterfile():
                with open(output_path, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk

            content_type = 'audio/mpeg' if request.type == 'audio' else 'video/mp4'
            
            return StreamingResponse(
                iterfile(),
                media_type=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename="video.{ext}"',
                    'Content-Length': str(file_size)
                }
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erreur générale: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Une erreur inattendue s'est produite: {str(e)}"
        )

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "2.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
