document.addEventListener('DOMContentLoaded', function() {
    const urlInput = document.getElementById('url');
    const typeSelect = document.getElementById('type');
    const qualitySelect = document.getElementById('quality');
    const qualityGroup = document.getElementById('qualityGroup');
    const downloadBtn = document.getElementById('downloadBtn');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const status = document.getElementById('status');
    const error = document.getElementById('error');
    const success = document.getElementById('success');
    const successText = document.getElementById('successText');
    const downloadLink = document.getElementById('downloadLink');

    // Gérer l'affichage du sélecteur de qualité
    typeSelect.addEventListener('change', function() {
        qualityGroup.style.display = this.value === 'video' ? 'block' : 'none';
    });

    // Fonction pour réinitialiser l'interface
    function resetInterface() {
        progressContainer.style.display = 'none';
        error.style.display = 'none';
        success.style.display = 'none';
        downloadLink.style.display = 'none';
        progressBar.style.width = '0%';
        downloadBtn.disabled = false;
        document.body.classList.remove('loading');
    }

    // Fonction pour afficher une erreur
    function showError(message) {
        error.textContent = message;
        error.style.display = 'block';
        progressContainer.style.display = 'none';
        downloadBtn.disabled = false;
        document.body.classList.remove('loading');
    }

    // Fonction pour démarrer le téléchargement
    async function startDownload() {
        try {
            const response = await fetch('/.netlify/functions/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: urlInput.value,
                    type: typeSelect.value,
                    quality: typeSelect.value === 'video' ? qualitySelect.value.replace('p', '') : 'best'
                })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Erreur lors du téléchargement');
            }

            const data = await response.json();
            
            // Créer un blob à partir du contenu base64
            const binaryContent = atob(data.content);
            const arrayBuffer = new ArrayBuffer(binaryContent.length);
            const uint8Array = new Uint8Array(arrayBuffer);
            
            for (let i = 0; i < binaryContent.length; i++) {
                uint8Array[i] = binaryContent.charCodeAt(i);
            }
            
            const blob = new Blob([arrayBuffer], { 
                type: typeSelect.value === 'audio' ? 'audio/mp3' : 'video/mp4' 
            });
            
            // Créer une URL pour le blob
            const blobUrl = URL.createObjectURL(blob);
            
            // Mettre à jour l'interface
            progressContainer.style.display = 'none';
            success.style.display = 'block';
            successText.textContent = 'Téléchargement terminé !';
            downloadLink.href = blobUrl;
            downloadLink.download = data.filename;
            downloadLink.style.display = 'inline-block';
            downloadBtn.disabled = false;
            document.body.classList.remove('loading');

        } catch (error) {
            showError(error.message);
        }
    }

    // Gestionnaire d'événement pour le formulaire
    downloadBtn.addEventListener('click', function(e) {
        e.preventDefault();

        if (!urlInput.value) {
            showError('Veuillez entrer une URL YouTube valide');
            return;
        }

        resetInterface();
        downloadBtn.disabled = true;
        document.body.classList.add('loading');
        progressContainer.style.display = 'block';
        status.textContent = 'Téléchargement en cours...';
        startDownload();
    });
});
