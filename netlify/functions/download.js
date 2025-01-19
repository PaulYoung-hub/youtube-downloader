const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const { v4: uuidv4 } = require('uuid');

exports.handler = async function(event, context) {
  // Log pour le débogage
  console.log('Function started');
  
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Method Not Allowed' })
    };
  }

  try {
    const { url, type, quality } = JSON.parse(event.body);
    console.log('Received parameters:', { url, type, quality });

    if (!url) {
      throw new Error('URL is required');
    }

    // Créer un ID unique pour ce téléchargement
    const downloadId = uuidv4();
    const tempDir = '/tmp/' + downloadId;
    
    // Créer le répertoire temporaire
    fs.mkdirSync(tempDir, { recursive: true });
    console.log('Created temp directory:', tempDir);

    // Chemin vers yt-dlp
    const ytDlpPath = path.join(process.env.LAMBDA_TASK_ROOT, 'bin', 'yt-dlp');
    console.log('yt-dlp path:', ytDlpPath);

    // Vérifier si yt-dlp existe
    if (!fs.existsSync(ytDlpPath)) {
      console.error('yt-dlp not found at:', ytDlpPath);
      throw new Error('yt-dlp not found');
    }

    // Configurer la commande
    let command = `${ytDlpPath} "${url}" -o "${path.join(tempDir, '%(title)s.%(ext)s')}" `;
    
    if (type === 'audio') {
      command += '--extract-audio --audio-format mp3 ';
    } else {
      const qualityValue = quality === 'highest' 
        ? 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' 
        : `bestvideo[height<=${quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<=${quality}][ext=mp4]/best[ext=mp4]`;
      command += `-f "${qualityValue}" `;
    }

    console.log('Executing command:', command);

    return new Promise((resolve, reject) => {
      exec(command, { maxBuffer: 1024 * 1024 * 50 }, (error, stdout, stderr) => {
        console.log('Command output:', stdout);
        console.log('Command errors:', stderr);

        if (error) {
          console.error('Download error:', error);
          resolve({
            statusCode: 500,
            headers: { 
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
              error: 'Download failed',
              details: error.message,
              stdout,
              stderr
            })
          });
          return;
        }

        try {
          const files = fs.readdirSync(tempDir);
          console.log('Files in temp directory:', files);

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
            headers: { 
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*'
            },
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
      headers: { 
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({
        error: 'Internal server error',
        details: error.message
      })
    };
  }
};
