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
import random
import json

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

class YTDLLogger:
    def debug(self, msg):
        if msg.startswith('[debug] '):
            logger.debug(msg)
    def info(self, msg):
        logger.info(msg)
    def warning(self, msg):
        logger.warning(msg)
    def error(self, msg):
        logger.error(msg)

def get_video_info(url: str) -> dict:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'logger': YTDLLogger(),
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des informations: {str(e)}")
            raise

def get_best_format(formats: list, type_: str, quality: str) -> str:
    if type_ == "audio":
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        if audio_formats:
            return max(audio_formats, key=lambda x: int(x.get('abr', 0)))['format_id']
        return 'bestaudio'
    
    if quality == "highest":
        return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    
    target_height = int(quality)
    video_formats = [
        f for f in formats 
        if f.get('height', 0) <= target_height 
        and f.get('ext', '') == 'mp4'
        and f.get('vcodec') != 'none'
    ]
    
    if video_formats:
        best_video = max(video_formats, key=lambda x: x.get('height', 0))
        return f"{best_video['format_id']}+bestaudio[ext=m4a]/best[ext=mp4]/best"
    
    return f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best'

@app.post("/api/download")
async def download_video(request: DownloadRequest):
    logger.info(f"Nouvelle requête de téléchargement: {request.dict()}")
    
    try:
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Extraire les informations de la vidéo d'abord
        try:
            video_info = get_video_info(request.url)
            logger.info(f"Informations vidéo extraites: {video_info.get('title')}")
        except Exception as e:
            if "Sign in to confirm you're not a bot" in str(e):
                raise HTTPException(
                    status_code=400,
                    detail="Cette vidéo nécessite une vérification. Essayez une autre vidéo ou revenez plus tard."
                )
            raise HTTPException(status_code=400, detail=str(e))

        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Dossier temporaire créé: {temp_dir}")
            
            ydl_opts = {
                'format': get_best_format(video_info.get('formats', []), request.type, request.quality),
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'logger': YTDLLogger(),
                'progress_hooks': [lambda d: logger.info(f"Progression: {d.get('status')} - {d.get('_percent_str', 'N/A')}")],
                'quiet': False,
                'no_warnings': True,
                'noplaylist': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                },
                'socket_timeout': 30,
                'retries': 10,
            }

            if request.type == "audio":
                ydl_opts.update({
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info("Début du téléchargement")
                    ydl.download([request.url])
                    
                    # Trouver le fichier téléchargé
                    files = os.listdir(temp_dir)
                    if not files:
                        raise HTTPException(status_code=404, detail="Aucun fichier n'a été téléchargé")
                    
                    filename = os.path.join(temp_dir, files[0])
                    logger.info(f"Fichier téléchargé: {filename}")

                    if not os.path.exists(filename):
                        raise HTTPException(status_code=404, detail="Le fichier n'a pas été trouvé après le téléchargement")

                    file_size = os.path.getsize(filename)
                    logger.info(f"Taille du fichier: {file_size} bytes")

                    def iterfile():
                        with open(filename, 'rb') as f:
                            while chunk := f.read(8192):
                                yield chunk

                    content_type = 'audio/mpeg' if request.type == 'audio' else 'video/mp4'
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
                error_msg = str(e)
                logger.error(f"Erreur lors du téléchargement: {error_msg}")
                
                if "Sign in to confirm you're not a bot" in error_msg:
                    raise HTTPException(
                        status_code=400,
                        detail="YouTube a détecté une activité inhabituelle. Essayez une autre vidéo ou attendez quelques minutes."
                    )
                elif "Video unavailable" in error_msg:
                    raise HTTPException(
                        status_code=400,
                        detail="Cette vidéo n'est pas disponible. Vérifiez l'URL et réessayez."
                    )
                elif "Private video" in error_msg:
                    raise HTTPException(
                        status_code=400,
                        detail="Cette vidéo est privée et ne peut pas être téléchargée."
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Erreur lors du téléchargement: {error_msg}"
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
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
