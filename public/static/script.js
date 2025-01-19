document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('downloadForm');
    const urlInput = document.getElementById('url');
    const typeSelect = document.getElementById('type');
    const qualitySelect = document.getElementById('quality');
    const downloadBtn = document.getElementById('downloadBtn');
    const message = document.getElementById('message');

    if (!form || !urlInput || !typeSelect || !qualitySelect || !downloadBtn || !message) {
        console.error('Certains éléments du formulaire sont manquants');
        return;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        try {
            message.textContent = 'Téléchargement en cours...';
            message.className = '';
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

            const contentType = response.headers.get('content-type');

            if (!response.ok) {
                let errorMessage = 'Erreur lors du téléchargement';
                if (contentType && contentType.includes('application/json')) {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorMessage;
                }
                throw new Error(errorMessage);
            }

            if (!contentType || (!contentType.includes('video/mp4') && !contentType.includes('audio/mpeg'))) {
                throw new Error('Format de réponse invalide');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = response.headers.get('content-disposition')
                ? response.headers.get('content-disposition').split('filename=')[1].replace(/"/g, '')
                : `download.${typeSelect.value === 'audio' ? 'mp3' : 'mp4'}`;
            
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            message.textContent = 'Téléchargement terminé !';
            message.className = 'success';
        } catch (error) {
            console.error('Error:', error);
            message.textContent = error.message;
            message.className = 'error';
        } finally {
            downloadBtn.disabled = false;
        }
    });

    typeSelect.addEventListener('change', () => {
        qualitySelect.style.display = typeSelect.value === 'video' ? 'block' : 'none';
    });
});
