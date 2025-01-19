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

@app.post("/api/download")
async def download_video(request: DownloadRequest):
    logger.info(f"Nouvelle requête de téléchargement: {request.dict()}")
    
    try:
        # Vérifier l'URL
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Créer un répertoire temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Dossier temporaire créé: {temp_dir}")
            
            # Configuration de base de yt-dlp avec des options anti-bot
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                # Options pour contourner les restrictions
                'cookiesfrombrowser': ('chrome',),  # Utilise les cookies de Chrome
                'extractor_args': {'youtube': {'player_client': ['android']}},
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                },
                'socket_timeout': 30,
            }

            # Configuration spécifique selon le type
            if request.type == "audio":
                logger.info("Configuration pour l'audio")
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                logger.info("Configuration pour la vidéo")
                if request.quality == "highest":
                    format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                else:
                    format_str = f'bestvideo[height<={request.quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={request.quality}][ext=mp4]/best'
                ydl_opts['format'] = format_str

            logger.info(f"Options yt-dlp: {ydl_opts}")

            try:
                # Télécharger la vidéo
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info("Début du téléchargement")
                    info = ydl.extract_info(request.url, download=True)
                    filename = ydl.prepare_filename(info)
                    logger.info(f"Fichier téléchargé: {filename}")

                    # Gérer l'extension pour l'audio
                    if request.type == "audio":
                        base = os.path.splitext(filename)[0]
                        filename = f"{base}.mp3"
                        logger.info(f"Fichier audio converti: {filename}")

                    # Vérifier si le fichier existe
                    if not os.path.exists(filename):
                        raise HTTPException(status_code=404, detail="File not found after download")

                    # Lire et retourner le fichier
                    file_size = os.path.getsize(filename)
                    logger.info(f"Taille du fichier: {file_size} bytes")

                    def iterfile():
                        with open(filename, 'rb') as f:
                            while chunk := f.read(8192):
                                yield chunk

                    # Déterminer le type de contenu
                    content_type = 'audio/mpeg' if request.type == 'audio' else 'video/mp4'
                    
                    # Obtenir le nom du fichier final
                    final_filename = os.path.basename(filename)

                    logger.info(f"Envoi du fichier: {final_filename}, type: {content_type}")
                    return StreamingResponse(
                        iterfile(),
                        media_type=content_type,
                        headers={
                            'Content-Disposition': f'attachment; filename="{final_filename}"',
                            'Content-Length': str(file_size)
                        }
                    )

            except Exception as e:
                logger.error(f"Erreur lors du téléchargement: {str(e)}")
                if "Sign in to confirm you're not a bot" in str(e):
                    raise HTTPException(
                        status_code=500,
                        detail="Cette vidéo nécessite une authentification. Essayez une autre vidéo ou revenez plus tard."
                    )
                raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

    except HTTPException as he:
        logger.error(f"HTTPException: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Erreur générale: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
