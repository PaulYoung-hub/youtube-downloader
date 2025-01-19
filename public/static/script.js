document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form');
    const urlInput = document.querySelector('#url');
    const typeSelect = document.querySelector('#type');
    const qualitySelect = document.querySelector('#quality');
    const downloadBtn = document.querySelector('#downloadBtn');
    const message = document.querySelector('#message');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        try {
            message.textContent = 'Téléchargement en cours...';
            downloadBtn.disabled = true;

            const response = await fetch('/.netlify/functions/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: urlInput.value,
                    type: typeSelect.value,
                    quality: qualitySelect.value
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Erreur lors du téléchargement');
            }

            if (data.success && data.downloadUrl) {
                // Créer un lien temporaire pour le téléchargement
                const downloadLink = document.createElement('a');
                downloadLink.href = data.downloadUrl;
                downloadLink.download = data.filename || 'video.mp4';
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
                
                message.textContent = 'Téléchargement démarré !';
            } else {
                throw new Error('Format non disponible');
            }
        } catch (error) {
            console.error('Error:', error);
            message.textContent = `Erreur: ${error.message}`;
        } finally {
            downloadBtn.disabled = false;
        }
    });

    // Gérer l'affichage du sélecteur de qualité
    typeSelect.addEventListener('change', () => {
        qualitySelect.style.display = typeSelect.value === 'video' ? 'block' : 'none';
    });
});
