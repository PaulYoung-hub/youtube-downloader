const fetch = require('node-fetch');

exports.handler = async function(event, context) {
  // Activer CORS
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };

  // Vérifier la méthode HTTP
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: 'Method Not Allowed' })
    };
  }

  try {
    const { url, type, quality } = JSON.parse(event.body);
    
    if (!url) {
      throw new Error('URL is required');
    }

    // Utiliser l'API rapidapi-youtube-dl
    const options = {
      method: 'GET',
      headers: {
        'X-RapidAPI-Key': '2b06f6414fmsh7d14c7bc0108a92p1c7d9djsnf3dabf8e3c07',
        'X-RapidAPI-Host': 'youtube-video-download-info.p.rapidapi.com'
      }
    };

    // Récupérer les informations de la vidéo
    const apiUrl = `https://youtube-video-download-info.p.rapidapi.com/dl?id=${getVideoId(url)}`;
    const response = await fetch(apiUrl, options);
    const data = await response.json();

    if (!response.ok) {
      throw new Error('Failed to fetch video info');
    }

    // Traiter les formats disponibles
    let downloadUrl;
    let filename;

    if (type === 'audio') {
      // Trouver le meilleur format audio
      const audioFormat = data.link.find(f => f.type === 'mp3' || f.type === 'm4a');
      if (!audioFormat) {
        throw new Error('No audio format available');
      }
      downloadUrl = audioFormat.url;
      filename = `${data.title}.${audioFormat.type}`;
    } else {
      // Trouver le format vidéo correspondant à la qualité demandée
      const videoFormats = data.link.filter(f => f.type === 'mp4');
      let selectedFormat;

      if (quality === 'highest') {
        selectedFormat = videoFormats.reduce((prev, current) => 
          (prev.quality > current.quality) ? prev : current
        );
      } else {
        selectedFormat = videoFormats.find(f => f.quality <= parseInt(quality)) ||
                        videoFormats[0];
      }

      if (!selectedFormat) {
        throw new Error('No suitable video format found');
      }
      downloadUrl = selectedFormat.url;
      filename = `${data.title}.mp4`;
    }

    // Retourner l'URL de téléchargement
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        success: true,
        downloadUrl,
        filename,
        title: data.title
      })
    };

  } catch (error) {
    console.error('Error:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({
        error: 'Internal server error',
        details: error.message
      })
    };
  }
};

// Fonction pour extraire l'ID de la vidéo YouTube
function getVideoId(url) {
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
  const match = url.match(regExp);
  return match && match[2].length === 11 ? match[2] : null;
}
