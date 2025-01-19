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

            const response = await fetch('/api/download', {
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

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erreur lors du téléchargement');
            }

            // Créer un blob à partir de la réponse
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = response.headers.get('content-disposition')
                ? response.headers.get('content-disposition').split('filename=')[1].replace(/"/g, '')
                : 'video.mp4';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            message.textContent = 'Téléchargement terminé !';
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
