const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { v4: uuidv4 } = require('uuid');

exports.handler = async function(event, context) {
  // Vérifier la méthode HTTP
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Method Not Allowed' })
    };
  }

  try {
    // Analyser le corps de la requête
    const { url, type, quality } = JSON.parse(event.body);
    
    // Vérifier les paramètres requis
    if (!url) {
      throw new Error('URL is required');
    }

    // Créer un ID unique pour ce téléchargement
    const downloadId = uuidv4();
    const tempDir = path.join('/tmp', downloadId);
    
    // Créer le répertoire temporaire
    fs.mkdirSync(tempDir, { recursive: true });

    // Configurer les options de yt-dlp
    const ytDlpPath = path.join(__dirname, 'yt-dlp');
    const outputTemplate = path.join(tempDir, '%(title)s.%(ext)s');
    
    // Construire la commande
    let command = `${ytDlpPath} "${url}" -o "${outputTemplate}" `;
    
    if (type === 'audio') {
      command += '--extract-audio --audio-format mp3 ';
    } else {
      const qualityValue = quality === 'highest' ? 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' 
                                               : `bestvideo[height<=${quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<=${quality}][ext=mp4]/best[ext=mp4]`;
      command += `-f "${qualityValue}" `;
    }

    console.log('Executing command:', command);

    return new Promise((resolve, reject) => {
      exec(command, { maxBuffer: 1024 * 1024 * 50 }, (error, stdout, stderr) => {
        console.log('stdout:', stdout);
        console.log('stderr:', stderr);
        
        if (error) {
          console.error('Error:', error);
          resolve({
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              error: 'Download failed',
              details: error.message,
              stdout: stdout,
              stderr: stderr
            })
          });
          return;
        }

        try {
          // Lire le fichier téléchargé
          const files = fs.readdirSync(tempDir);
          if (files.length === 0) {
            throw new Error('No file was downloaded');
          }

          const downloadedFile = files[0];
          const filePath = path.join(tempDir, downloadedFile);
          const fileContent = fs.readFileSync(filePath);
          
          // Nettoyer
          try {
            fs.rmSync(tempDir, { recursive: true, force: true });
          } catch (cleanupError) {
            console.error('Cleanup error:', cleanupError);
          }

          // Renvoyer le contenu
          resolve({
            statusCode: 200,
            headers: { 
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
              success: true,
              filename: downloadedFile,
              content: fileContent.toString('base64')
            })
          });
        } catch (fileError) {
          console.error('File handling error:', fileError);
          resolve({
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              error: 'File processing failed',
              details: fileError.message
            })
          });
        }
      });
    });

  } catch (error) {
    console.error('General error:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        error: 'Internal server error',
        details: error.message
      })
    };
  }
};
