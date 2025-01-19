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

# Liste des User-Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
]

class DownloadRequest(BaseModel):
    url: str
    type: str
    quality: Optional[str] = "720"

def get_format_options(type_: str, quality: str) -> dict:
    if type_ == "audio":
        return {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        if quality == "highest":
            format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            format_str = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best'
        return {'format': format_str}

@app.post("/api/download")
async def download_video(request: DownloadRequest):
    logger.info(f"Nouvelle requête de téléchargement: {request.dict()}")
    
    try:
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required")

        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Dossier temporaire créé: {temp_dir}")
            
            # Configuration de base
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'http_headers': {
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'DNT': '1',
                },
                'socket_timeout': 30,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'logtostderr': False,
                'cachedir': False,
                'extractor_retries': 3,
                'file_access_retries': 3,
                'fragment_retries': 3,
                'skip_download': False,
                'overwrites': True,
                'verbose': True,
            }

            # Ajouter les options spécifiques au format
            format_opts = get_format_options(request.type, request.quality)
            ydl_opts.update(format_opts)

            logger.info(f"Options yt-dlp: {ydl_opts}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info("Début du téléchargement")
                    info = ydl.extract_info(request.url, download=True)
                    filename = ydl.prepare_filename(info)
                    logger.info(f"Fichier téléchargé: {filename}")

                    if request.type == "audio":
                        base = os.path.splitext(filename)[0]
                        filename = f"{base}.mp3"
                        logger.info(f"Fichier audio converti: {filename}")

                    if not os.path.exists(filename):
                        raise HTTPException(status_code=404, detail="File not found after download")

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
                        status_code=500,
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
                    raise HTTPException(status_code=500, detail=f"Erreur de téléchargement: {error_msg}")

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
