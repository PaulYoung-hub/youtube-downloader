from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
from threading import Thread
import uuid
import logging
import time
from urllib.parse import urlparse
import secrets

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Génération d'une clé secrète aléatoire de 32 bytes
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['DOWNLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

# Dictionnaire pour stocker les progressions des téléchargements
download_progress = {}

def sanitize_filename(filename):
    """Nettoyer le nom de fichier des caractères non autorisés."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/progress/<download_id>')
def get_progress(download_id):
    progress = download_progress.get(download_id, {})
    logger.debug(f"Progress for {download_id}: {progress}")
    return jsonify(progress)

def my_hook(d, download_id):
    if d['status'] == 'downloading':
        try:
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            if total_bytes:
                percentage = (downloaded_bytes / total_bytes) * 100
                download_progress[download_id].update({
                    'status': 'downloading',
                    'progress': percentage,
                    'speed': d.get('speed', 0),
                    'eta': d.get('eta', 0)
                })
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la progression: {str(e)}")
    elif d['status'] == 'finished':
        download_progress[download_id].update({
            'status': 'processing',
            'progress': 100
        })

def get_ydl_opts(quality, download_type, download_id, filename_template):
    """Configure les options de yt-dlp en fonction du type de téléchargement."""
    ydl_opts = {
        'outtmpl': filename_template,
        'progress_hooks': [lambda d: my_hook(d, download_id)],
        'quiet': True,
        'no_warnings': True,
    }

    if download_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:  # video
        if quality == 'highest':
            format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            try:
                max_height = int(quality.rstrip('p'))
                format_str = f'bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_height}][ext=mp4]/best'
            except (ValueError, AttributeError):
                format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        
        ydl_opts.update({
            'format': format_str,
            'merge_output_format': 'mp4'
        })
    
    return ydl_opts

def download_file(url, quality, download_type, download_id):
    try:
        logger.info(f"Démarrage du téléchargement: URL={url}, quality={quality}, type={download_type}")
        
        # Créer le template de nom de fichier
        filename_template = os.path.join(app.config['DOWNLOAD_FOLDER'], '%(title)s.%(ext)s')
        
        # Obtenir les options de yt-dlp
        ydl_opts = get_ydl_opts(quality, download_type, download_id, filename_template)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Extraire les informations de la vidéo
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise Exception("Impossible d'obtenir les informations de la vidéo")
                
                # Obtenir le titre et créer le nom de fichier
                video_title = info.get('title', f'video_{download_id}')
                filename = sanitize_filename(video_title)
                
                # Déterminer l'extension finale
                extension = 'mp3' if download_type == 'audio' else 'mp4'
                final_path = os.path.join(app.config['DOWNLOAD_FOLDER'], f"{filename}.{extension}")
                
                # Vérifier que le fichier existe
                if not os.path.exists(final_path):
                    raise Exception("Le fichier n'a pas été téléchargé correctement")
                
                # Mettre à jour le statut final
                download_progress[download_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'filename': os.path.basename(final_path),
                    'title': video_title
                })
                
                logger.info(f"Téléchargement terminé avec succès: {final_path}")
                
            except Exception as e:
                raise Exception(f"Erreur pendant le téléchargement: {str(e)}")
                
    except Exception as e:
        error_msg = f"Erreur: {str(e)}"
        logger.error(error_msg)
        download_progress[download_id] = {
            'status': 'error',
            'error': error_msg
        }

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.json.get('url')
        quality = request.json.get('quality', 'highest')
        download_type = request.json.get('type', 'video')

        logger.info(f"Nouvelle demande de téléchargement: URL={url}, quality={quality}, type={download_type}")

        if not url:
            return jsonify({'error': 'URL requise'}), 400

        # Vérifier que l'URL est valide
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return jsonify({'error': 'URL invalide'}), 400
        except Exception:
            return jsonify({'error': 'URL invalide'}), 400

        download_id = str(uuid.uuid4())
        download_progress[download_id] = {
            'status': 'starting',
            'progress': 0
        }
        
        thread = Thread(target=download_file, args=(url, quality, download_type, download_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'download_id': download_id
        })

    except Exception as e:
        logger.error(f"Erreur lors du téléchargement: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-file/<filename>')
def get_file(filename):
    try:
        file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        logger.info(f"Envoi du fichier: {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"Fichier non trouvé: {file_path}")
            return jsonify({'error': 'Fichier non trouvé'}), 404
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du fichier: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
    logger.info(f"Dossier de téléchargement: {app.config['DOWNLOAD_FOLDER']}")
    app.run(debug=True)
