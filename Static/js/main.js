document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const imageInput = document.getElementById('imageInput');
    const uploadProgress = document.getElementById('uploadProgress');
    const resultsSection = document.getElementById('resultsSection');
    const originalImage = document.getElementById('originalImage');
    const processedImage = document.getElementById('processedImage');

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
            const response = await fetch('/process_image', {
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

    // Function to display processing results
    function displayResults(data) {
        // Show results section
        resultsSection.style.display = 'block';

        // Display images
        originalImage.src = data.original_path;
        processedImage.src = data.output_image;  // Use the merged visualization
        
        // Add error handling for image loading
        processedImage.onerror = function() {
            console.error('Failed to load processed image');
            processedImage.src = '/Static/images/error.png';  // You might want to add a placeholder error image
            processedImage.alt = 'Error loading processed image';
        };
    }
}); 