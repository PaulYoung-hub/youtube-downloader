from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import tempfile
from typing import Optional
import asyncio
import aiofiles

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
    try:
        # Créer un répertoire temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            # Configuration de yt-dlp
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }

            if request.type == "audio":
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                # Configuration pour la vidéo
                if request.quality != "highest":
                    ydl_opts['format'] = f'bestvideo[height<={request.quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={request.quality}][ext=mp4]/best'

            # Télécharger la vidéo
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(request.url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Gérer l'extension pour l'audio
                if request.type == "audio":
                    filename = os.path.splitext(filename)[0] + '.mp3'

                # Vérifier si le fichier existe
                if not os.path.exists(filename):
                    raise HTTPException(status_code=404, detail="File not found after download")

                # Lire et retourner le fichier
                async def iterfile():
                    async with aiofiles.open(filename, 'rb') as f:
                        while chunk := await f.read(8192):
                            yield chunk

                # Déterminer le type de contenu
                content_type = 'audio/mpeg' if request.type == 'audio' else 'video/mp4'
                
                # Obtenir le nom du fichier final
                final_filename = os.path.basename(filename)

                return StreamingResponse(
                    iterfile(),
                    media_type=content_type,
                    headers={
                        'Content-Disposition': f'attachment; filename="{final_filename}"'
                    }
                )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# Route racine pour vérifier que l'API fonctionne
@app.get("/")
async def root():
    return {"status": "API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
