document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const imageInput = document.getElementById('imageInput');
    const uploadProgress = document.getElementById('uploadProgress');
    const resultsSection = document.getElementById('resultsSection');
    const originalImage = document.getElementById('originalImage');
    const processedImage = document.getElementById('processedImage');
    const elementsContainer = document.getElementById('elementsContainer');
    const resultName = document.getElementById('resultName');
    const saveButton = document.getElementById('saveButton');
    const savedResults = document.getElementById('savedResults');

    // Load saved results on page load
    loadSavedResults();

    // Handle file upload
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const file = imageInput.files[0];
        if (!file) {
            alert('Please select an image file');
            return;
        }

        // Validate file type
        const allowedTypes = ['image/jpeg', 'image/png', 'image/jpg'];
        if (!allowedTypes.includes(file.type)) {
            alert('Please select a valid image file (JPEG or PNG)');
            return;
        }

        // Validate file size (max 16MB)
        const maxSize = 16 * 1024 * 1024; // 16MB in bytes
        if (file.size > maxSize) {
            alert('File is too large. Maximum size is 16MB');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        // Show progress bar
        uploadProgress.style.display = 'block';
        uploadProgress.querySelector('.progress').style.width = '50%';

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            if (data.error) {
                throw new Error(data.error);
            }
            
            // Update progress
            uploadProgress.querySelector('.progress').style.width = '100%';

            // Display results
            displayResults(data);

            // Reset form
            uploadForm.reset();

            // Hide progress after a delay
            setTimeout(() => {
                uploadProgress.style.display = 'none';
                uploadProgress.querySelector('.progress').style.width = '0';
            }, 1000);

        } catch (error) {
            console.error('Error:', error);
            alert('Error processing image: ' + error.message);
            uploadProgress.style.display = 'none';
            uploadProgress.querySelector('.progress').style.width = '0';
        }
    });

    // Handle saving results
    saveButton.addEventListener('click', async function() {
        const name = resultName.value.trim();
        if (!name) {
            alert('Please enter a name for these results');
            return;
        }

        // Get current results data
        const elements = Array.from(elementsContainer.querySelectorAll('.element-card')).map(card => ({
            id: card.dataset.id,
            text: card.querySelector('textarea').value
        }));

        try {
            const response = await fetch('/api/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: name,
                    original_path: originalImage.dataset.path,
                    processed_path: processedImage.dataset.path,
                    json_data: {
                        elements: elements
                    }
                })
            });

            if (!response.ok) {
                throw new Error('Save failed');
            }

            alert('Results saved successfully!');
            resultName.value = '';
            loadSavedResults();

        } catch (error) {
            console.error('Error:', error);
            alert('Error saving results: ' + error.message);
        }
    });

    // Function to display processing results
    function displayResults(data) {
        // Show results section
        resultsSection.style.display = 'block';

        // Display images
        originalImage.src = `/api/image/${encodeURIComponent(data.original_path)}`;
        originalImage.dataset.path = data.original_path;
        processedImage.src = `/api/image/${encodeURIComponent(data.image_path)}`;
        processedImage.dataset.path = data.image_path;

        // Load and display JSON data
        fetch(data.json_path)
            .then(response => response.json())
            .then(jsonData => {
                displayElements(jsonData);
            })
            .catch(error => {
                console.error('Error loading JSON data:', error);
            });
    }

    // Function to display detected elements
    function displayElements(data) {
        elementsContainer.innerHTML = '';

        // Display cells with text
        data.cells_with_text.forEach(cell => {
            const card = document.createElement('div');
            card.className = 'element-card';
            card.dataset.id = cell.cell_id;

            const textarea = document.createElement('textarea');
            textarea.value = cell.text;
            textarea.placeholder = 'Enter text...';

            const confidence = document.createElement('div');
            confidence.className = 'confidence';
            confidence.textContent = `Confidence: ${(cell.confidence * 100).toFixed(1)}%`;

            card.appendChild(textarea);
            card.appendChild(confidence);
            elementsContainer.appendChild(card);
        });
    }

    // Function to load saved results
    async function loadSavedResults() {
        try {
            const response = await fetch('/api/results');
            if (!response.ok) {
                throw new Error('Failed to load results');
            }

            const results = await response.json();
            displaySavedResults(results);

        } catch (error) {
            console.error('Error:', error);
            savedResults.innerHTML = '<p>Error loading saved results</p>';
        }
    }

    // Function to display saved results
    function displaySavedResults(results) {
        savedResults.innerHTML = '';

        results.forEach(result => {
            const card = document.createElement('div');
            card.className = 'result-card';

            const name = document.createElement('h3');
            name.textContent = result.name;

            const image = document.createElement('img');
            image.src = `/api/image/${encodeURIComponent(result.processed_image)}`;
            image.alt = result.name;

            const timestamp = document.createElement('div');
            timestamp.className = 'timestamp';
            timestamp.textContent = new Date(result.timestamp).toLocaleString();

            card.appendChild(name);
            card.appendChild(image);
            card.appendChild(timestamp);
            savedResults.appendChild(card);
        });

        if (results.length === 0) {
            savedResults.innerHTML = '<p>No saved results yet</p>';
        }
    }
}); 