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

    // Fonction pour mettre à jour la progression
    function updateProgress(progress) {
        if (progress.status === 'downloading') {
            progressBar.style.width = `${progress.progress}%`;
            if (progress.speed) {
                const speed = (progress.speed / 1024 / 1024).toFixed(2);
                const eta = progress.eta ? `${progress.eta} secondes restantes` : '';
                status.textContent = `Téléchargement en cours... ${progress.progress.toFixed(1)}% (${speed} MB/s) ${eta}`;
            } else {
                status.textContent = `Téléchargement en cours... ${progress.progress.toFixed(1)}%`;
            }
        } else if (progress.status === 'processing') {
            progressBar.style.width = '100%';
            status.textContent = 'Traitement en cours...';
        } else if (progress.status === 'completed') {
            progressContainer.style.display = 'none';
            success.style.display = 'block';
            successText.textContent = 'Téléchargement terminé !';
            downloadLink.href = `/get-file/${progress.filename}`;
            downloadLink.style.display = 'inline-block';
            downloadBtn.disabled = false;
            document.body.classList.remove('loading');
        } else if (progress.status === 'error') {
            showError(progress.error);
        }
    }

    // Fonction pour démarrer le téléchargement
    async function startDownload() {
        try {
            const response = await fetch('/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: urlInput.value,
                    type: typeSelect.value,
                    quality: typeSelect.value === 'video' ? qualitySelect.value : 'highest'
                })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Erreur lors du téléchargement');
            }

            const data = await response.json();
            const downloadId = data.download_id;

            // Démarrer la vérification de la progression
            const progressCheck = setInterval(async () => {
                try {
                    const progressResponse = await fetch(`/progress/${downloadId}`);
                    const progressData = await progressResponse.json();
                    updateProgress(progressData);

                    if (['completed', 'error'].includes(progressData.status)) {
                        clearInterval(progressCheck);
                    }
                } catch (error) {
                    console.error('Erreur lors de la vérification de la progression:', error);
                }
            }, 1000);

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
        status.textContent = 'Initialisation du téléchargement...';
        startDownload();
    });
});
