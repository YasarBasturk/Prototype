// Global variables to store current processing results
let currentJsonData = null;
let currentOriginalPath = null;
let currentOutputImage = null;

// Track edited items
const editedItems = new Set();

// Initialize modals
let documentNameModal = null;
let documentsListModal = null;
let documentViewModal = null;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap modals
    documentNameModal = new bootstrap.Modal(document.getElementById('documentNameModal'));
    documentsListModal = new bootstrap.Modal(document.getElementById('documentsListModal'));
    documentViewModal = new bootstrap.Modal(document.getElementById('documentViewModal'));
    
    // Add event listener for save results button
    document.getElementById('saveResultsBtn').addEventListener('click', function() {
        documentNameModal.show();
    });
    
    // Add event listener for confirm save button
    document.getElementById('confirmSaveBtn').addEventListener('click', function() {
        const documentName = document.getElementById('documentName').value.trim() || 'Unnamed Document';
        saveDocumentToDatabase(documentName);
        documentNameModal.hide();
    });
    
    // Add event listener for view documents button
    document.getElementById('viewDocumentsBtn').addEventListener('click', function() {
        loadDocumentsList();
        documentsListModal.show();
    });
    
    // Add event listener for back to documents button
    document.getElementById('backToDocumentsBtn').addEventListener('click', function() {
        documentViewModal.hide();
        loadDocumentsList();
        documentsListModal.show();
    });

    // Add threshold slider event listener
    const thresholdSlider = document.getElementById('confidenceThreshold');
    const thresholdValue = document.getElementById('thresholdValue');
    
    thresholdSlider.addEventListener('input', function() {
        thresholdValue.textContent = this.value + '%';
        updateVisibleTextItems();
    });

    function updateVisibleTextItems() {
        const threshold = thresholdSlider.value / 100;
        const textItems = document.querySelectorAll('.text-item');
        
        textItems.forEach(item => {
            const confidenceSpan = item.querySelector('.badge');
            const confidence = parseInt(confidenceSpan.textContent) / 100;
            
            if (confidence < threshold) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // Initial update
    updateVisibleTextItems();
});

document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const spinner = document.getElementById('spinner');
    
    try {
        spinner.classList.remove('d-none');
        
        const response = await fetch('/process_image', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Store current processing results
            currentJsonData = data.json_data;
            currentOriginalPath = data.original_path;
            currentOutputImage = data.output_image;
            
            // Display original image
            document.getElementById('originalImageContainer').innerHTML = `
                <img src="${data.original_path}" class="img-fluid" alt="Original Image">
            `;
            
            // Display processed image with legend
            document.getElementById('processedImageContainer').innerHTML = `
                <img src="${data.output_image}" class="img-fluid" alt="Analysis Visualization">
                <div class="visualization-legend mt-3">
                    <h6>Visualization Legend</h6>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(0, 255, 0);"></span>
                        <span class="ms-2">Cells with text (green)</span>
                    </div>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(255, 0, 0);"></span>
                        <span class="ms-2">Empty cells (red)</span>
                    </div>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(128, 0, 128);"></span>
                        <span class="ms-2">Cells with spanning text (purple)</span>
                    </div>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(0, 255, 255);"></span>
                        <span class="ms-2">Text spanning connector lines (yellow)</span>
                    </div>
                    <div class="d-flex align-items-center">
                        <span class="legend-color-box" style="background-color: rgb(255, 0, 0);"></span>
                        <span class="ms-2">Unassigned text (blue)</span>
                    </div>
                </div>
            `;
            
            // Display JSON data
            displayJsonData(data.json_data);
            
            // Show save results button
            document.getElementById('saveResultsBtn').classList.remove('d-none');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error uploading file: ' + error);
    } finally {
        spinner.classList.add('d-none');
    }
});

function displayJsonData(data) {
    // Display metadata
    const metadata = Object.entries(data.metadata)
        .map(([key, value]) => `
            <div class="col-md-4 mb-3">
                <div class="card h-100">
                    <div class="card-body">
                        <h6 class="card-subtitle mb-2 text-muted">${key}</h6>
                        <p class="card-text">${value}</p>
                    </div>
                </div>
            </div>
        `).join('');
    
    // Display cells with text
    const cellsWithText = data.cells_with_text.map(cell => `
        <div class="col-md-6 mb-3">
            <div class="card h-100 text-item" data-type="cell" data-id="${cell.cell_id}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span>Cell #${cell.cell_id}</span>
                    <span class="badge ${getConfidenceBadgeClass(cell.confidence)}">
                        ${Math.round(cell.confidence * 100)}%
                    </span>
                </div>
                <div class="card-body">
                    <div class="text-content" id="cell-${cell.cell_id}" data-original-text="${cell.text}">
                        ${cell.text}
                    </div>
                    ${cell.component_texts ? cell.component_texts.map((component, index) => `
                        <div class="component-text mt-2">
                            <small class="text-muted">Component ${index + 1}</small>
                            <div class="text-content" data-component-id="${index}">
                                ${component.text}
                            </div>
                            <small class="text-muted">Confidence: ${Math.round(component.confidence * 100)}%</small>
                        </div>
                    `).join('') : ''}
                </div>
                <div class="card-footer">
                    <button class="btn btn-sm btn-outline-primary btn-edit">Edit</button>
                    <button class="btn btn-sm btn-outline-secondary btn-revert d-none">Revert</button>
                </div>
            </div>
        </div>
    `).join('');
    
    // Display unassigned text
    const unassignedText = data.unassigned_text.map(text => `
        <div class="col-md-6 mb-3">
            <div class="card h-100 text-item" data-type="text" data-id="${text.text_id}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span>Text #${text.text_id}</span>
                    <span class="badge ${getConfidenceBadgeClass(text.confidence)}">
                        ${Math.round(text.confidence * 100)}%
                    </span>
                </div>
                <div class="card-body">
                    <div class="text-content" id="text-${text.text_id}" data-original-text="${text.text}">
                        ${text.text}
                    </div>
                </div>
                <div class="card-footer">
                    <button class="btn btn-sm btn-outline-primary btn-edit">Edit</button>
                    <button class="btn btn-sm btn-outline-secondary btn-revert d-none">Revert</button>
                </div>
            </div>
        </div>
    `).join('');
    
    // Combine all sections
    document.getElementById('textResults').innerHTML = `
        <div class="mb-4">
            <h4 class="mb-3">Document Statistics</h4>
            <div class="row">
                ${metadata}
            </div>
        </div>
        <div class="mb-4">
            <h4 class="mb-3">Cells with Text</h4>
            <div class="row">
                ${cellsWithText}
            </div>
        </div>
        <div class="mb-4">
            <h4 class="mb-3">Unassigned Text</h4>
            <div class="row">
                ${unassignedText}
            </div>
        </div>
    `;
    
    // Add event listeners to edit buttons
    document.querySelectorAll('.btn-edit').forEach(btn => {
        btn.addEventListener('click', handleEditClick);
    });
    
    // Add event listeners to revert buttons
    document.querySelectorAll('.btn-revert').forEach(btn => {
        btn.addEventListener('click', handleRevertClick);
    });
}

function handleEditClick() {
    const card = this.closest('.card');
    const textContent = card.querySelector('.text-content');
    const currentText = textContent.textContent.trim();
    const revertBtn = card.querySelector('.btn-revert');
    
    // Add editing class
    textContent.classList.add('editing');
            
    // Convert to editable textarea
    textContent.innerHTML = `
        <div class="edit-controls">
            <textarea class="form-control edit-textarea" rows="3">${currentText}</textarea>
            <div class="d-flex mt-2">
                <button class="btn btn-sm btn-outline-secondary me-2 cancel-edit">Cancel</button>
                <button class="btn btn-sm btn-outline-success save-edit">Save</button>
            </div>
        </div>
    `;
    
    // Hide the edit button while editing
    this.style.display = 'none';
            
    // Add event listeners to cancel and save buttons
    const cancelBtn = textContent.querySelector('.cancel-edit');
    const saveBtn = textContent.querySelector('.save-edit');
    
    cancelBtn.addEventListener('click', function() {
        // Restore the original content
        textContent.innerHTML = currentText;
        // Remove editing class
        textContent.classList.remove('editing');
        // Show the edit button again
        card.querySelector('.btn-edit').style.display = 'inline-block';
    });
    
    saveBtn.addEventListener('click', function() {
        const newText = textContent.querySelector('.edit-textarea').value;
        // Remove editing class
        textContent.classList.remove('editing');
        // Update the displayed text
        textContent.innerHTML = newText;
        
        // Store original text if this is the first edit
        if (!textContent.dataset.edited) {
            textContent.dataset.edited = "true";
            // Make revert button visible
            revertBtn.classList.remove('d-none');
        }
        
        // Show the edit button again
        card.querySelector('.btn-edit').style.display = 'inline-block';
        
        // Mark the item as edited
        card.classList.add('edited');
        
        // Save changes to the data and server
        saveTextChange(card, newText);
    });
}

function handleRevertClick() {
    const card = this.closest('.card');
    const textContent = card.querySelector('.text-content');
    const originalText = textContent.dataset.originalText;
    
    // Confirm before reverting
    if (confirm('Are you sure you want to revert this text to its original value?')) {
        // Restore the original text
        textContent.innerHTML = originalText;
        
        // Remove the edited flag
        textContent.dataset.edited = '';
        card.classList.remove('edited');
        
        // Hide the revert button
        this.classList.add('d-none');
        
        // Save the reverted text
        saveTextChange(card, originalText);
    }
}

function saveTextChange(card, newText) {
    const itemType = card.dataset.type;
    const itemId = parseInt(card.dataset.id);
    const textContent = card.querySelector('.text-content');
    
    const changes = {
        cells_with_text: [],
        unassigned_text: []
    };

    if (itemType === 'cell') {
        changes.cells_with_text.push({
            cell_id: itemId,
            text: newText
        });
        
        // Update current JSON data
        if (currentJsonData && currentJsonData.cells_with_text) {
            const cellIndex = currentJsonData.cells_with_text.findIndex(cell => cell.cell_id === itemId);
            if (cellIndex !== -1) {
                currentJsonData.cells_with_text[cellIndex].text = newText;
                editedItems.add(`cell_${itemId}`);
            }
        }
    } else if (itemType === 'text') {
        changes.unassigned_text.push({
            text_id: itemId,
            text: newText
        });
        
        // Update current JSON data
        if (currentJsonData && currentJsonData.unassigned_text) {
            const textIndex = currentJsonData.unassigned_text.findIndex(text => text.text_id === itemId);
            if (textIndex !== -1) {
                currentJsonData.unassigned_text[textIndex].text = newText;
                editedItems.add(`text_${itemId}`);
            }
        }
    }

    // Get the filename from the processed image URL
    const processedImage = document.getElementById('processedImageContainer').querySelector('img');
    if (!processedImage) {
        console.error('Processed image not found');
        showErrorMessage(textContent, 'Could not determine JSON file path');
        return;
    }
    
    // Show a saving indicator
    const savingIndicator = document.createElement('div');
    savingIndicator.className = 'save-indicator info';
    savingIndicator.textContent = 'Saving...';
    textContent.appendChild(savingIndicator);
    
    // Extract base filename to use with find_json endpoint
    const extractBaseFilename = () => {
        let imageSrc = processedImage.src;
        let parts = imageSrc.split('/');
        let imageFilename = parts[parts.length - 1];
        
        console.log('Image filename:', imageFilename);
        
        // Extract the base prefix (usually processed_XXX)
        let basePrefix;
        
        if (imageFilename.startsWith('visualization_')) {
            // Remove visualization_ prefix
            basePrefix = imageFilename.replace('visualization_', '').split('.')[0];
            // If it contains _res_, keep only the part before it
            if (basePrefix.includes('_res_')) {
                basePrefix = basePrefix.split('_res_')[0];
            }
        } 
        else if (imageFilename.includes('_res_')) {
            // If it contains _res_, keep only the part before it
            basePrefix = imageFilename.split('_res_')[0];
        }
        else {
            // Just use the filename without extension
            basePrefix = imageFilename.split('.')[0];
        }
        
        console.log('Extracted base prefix:', basePrefix);
        return basePrefix;
    };
    
    // Get the base filename to search for
    const basePrefix = extractBaseFilename();
    
    // Use the find_json endpoint to get the correct JSON filename
    fetch(`/find_json/${basePrefix}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data.success) {
                throw new Error(data.error || 'Failed to find JSON file');
            }
            
            console.log('Available JSON files:', data.files);
            console.log('Matching files:', data.matching_files);
            
            // Use the best match if available, otherwise fall back to first matching file
            let jsonFilename = data.best_match;
            
            if (!jsonFilename && data.matching_files && data.matching_files.length > 0) {
                jsonFilename = data.matching_files[0];
                console.log('Using first matching file:', jsonFilename);
            }
            
            if (!jsonFilename) {
                throw new Error('No matching JSON file found');
            }
            
            console.log('Using JSON file:', jsonFilename);
            
            // Now save the changes using the found filename
            return fetch('/save_edits/' + jsonFilename, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(changes)
            });
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Remove the saving indicator
            savingIndicator.remove();
            
            if (data.success) {
                console.log('Changes saved successfully!', data);
                
                // Add visual indicator that the change was saved
                const saveIndicator = document.createElement('div');
                saveIndicator.className = 'save-indicator success';
                saveIndicator.textContent = 'Changes saved';
                textContent.appendChild(saveIndicator);
                
                // Fade out and remove after 3 seconds
                setTimeout(() => {
                    saveIndicator.style.opacity = '0';
                    setTimeout(() => saveIndicator.remove(), 1000);
                }, 2000);
            } else {
                console.error('Error saving changes:', data.error);
                showErrorMessage(textContent, data.error || 'Unknown error saving changes');
            }
        })
        .catch(error => {
            console.error('Error saving changes:', error);
            
            // Remove the saving indicator
            savingIndicator.remove();
            
            // Show error message
            showErrorMessage(textContent, error.message);
            
            // If the error was due to not finding a file, try the fallback method
            if (error.message.includes('No matching') || error.message.includes('not found')) {
                console.log('Trying fallback method');
                handleFileNotFoundError(textContent, basePrefix + '.json', changes);
            }
        });
}

function showErrorMessage(container, message) {
    // Create error message
    const errorMsg = document.createElement('div');
    errorMsg.className = 'save-indicator error';
    errorMsg.textContent = `Error: ${message}`;
    container.appendChild(errorMsg);
    
    // Fade out and remove after 5 seconds
    setTimeout(() => {
        errorMsg.style.opacity = '0';
        setTimeout(() => errorMsg.remove(), 1000);
    }, 4000);
}

function getConfidenceBadgeClass(confidence) {
    if (confidence >= 0.8) return 'bg-success';
    if (confidence >= 0.5) return 'bg-warning';
    return 'bg-danger';
}

function saveDocumentToDatabase(documentName) {
    // Prepare data for saving
    const saveData = {
        document_name: documentName,
        original_image_path: currentOriginalPath,
        output_image_path: currentOutputImage,
        json_data: currentJsonData,
        edited_items: Array.from(editedItems)
    };
    
    // Send data to server
    fetch('/save_results', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(saveData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`Document "${documentName}" saved successfully!`);
        } else {
            alert('Error saving document: ' + data.error);
        }
    })
    .catch(error => {
        alert('Error saving document: ' + error);
    });
}

function loadDocumentsList() {
    const tableBody = document.getElementById('documentsTableBody');
    tableBody.innerHTML = '<tr><td colspan="4" class="text-center">Loading documents...</td></tr>';
    
    fetch('/get_documents')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.documents) {
                if (data.documents.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="4" class="text-center">No documents found</td></tr>';
                    return;
                }
                
                tableBody.innerHTML = '';
                data.documents.forEach(doc => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${doc.document_name}</td>
                        <td>${new Date(doc.created_at).toLocaleString()}</td>
                        <td>${doc.text_count || 0}</td>
                        <td>
                            <button class="btn btn-sm btn-primary view-document" data-document-id="${doc.id}">
                                <i class="bi bi-eye"></i> View
                            </button>
                        </td>
                    `;
                    tableBody.appendChild(row);
                });
                
                // Add event listeners to view buttons
                document.querySelectorAll('.view-document').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const documentId = this.dataset.documentId;
                        viewDocument(documentId);
                    });
                });
            } else {
                tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Error: ${data.error || 'Failed to load documents'}</td></tr>`;
            }
        })
        .catch(error => {
            tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Error: ${error.message}</td></tr>`;
        });
}

function viewDocument(documentId) {
    fetch(`/get_document/${documentId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.document) {
                const doc = data.document;
                
                // Display document info
                const infoTable = document.getElementById('documentInfoTable');
                infoTable.innerHTML = `
                    <tr><th>Document Name</th><td>${doc.document_name}</td></tr>
                    <tr><th>Created</th><td>${new Date(doc.created_at).toLocaleString()}</td></tr>
                    <tr><th>Filename</th><td>${doc.filename || 'N/A'}</td></tr>
                    <tr><th>Document ID</th><td>${doc.id}</td></tr>
                `;
                
                // Display document image
                const imageContainer = document.getElementById('documentImage');
                if (doc.original_image_path) {
                    imageContainer.innerHTML = `<img src="/${doc.original_image_path}" class="img-fluid" alt="Original Image">`;
                } else {
                    imageContainer.innerHTML = `<p class="text-muted">No image available</p>`;
                }
                
                // Display text items
                const textItemsTable = document.getElementById('textItemsTableBody');
                textItemsTable.innerHTML = '';
                
                if (doc.text_items && doc.text_items.length > 0) {
                    doc.text_items.forEach(item => {
                        const row = document.createElement('tr');
                        const region = JSON.parse(item.text_region || '{}');
                        const regionType = region.cell_id !== undefined ? `Cell #${region.cell_id}` : 
                                        region.text_id !== undefined ? `Text #${region.text_id}` : 'Unknown';
                        
                        row.innerHTML = `
                            <td>${item.id}</td>
                            <td>${item.text}</td>
                            <td>${item.confidence ? Math.round(item.confidence * 100) + '%' : 'N/A'}</td>
                            <td>${regionType}</td>
                            <td>${item.edited ? '<span class="badge bg-success">Yes</span>' : '<span class="badge bg-secondary">No</span>'}</td>
                        `;
                        textItemsTable.appendChild(row);
                    });
                } else {
                    textItemsTable.innerHTML = '<tr><td colspan="5" class="text-center">No text items found</td></tr>';
                }
                
                // Update modal title
                document.getElementById('documentViewModalLabel').textContent = `Document: ${doc.document_name}`;
                
                // Hide documents list modal and show document view modal
                documentsListModal.hide();
                documentViewModal.show();
            } else {
                alert('Error: ' + (data.error || 'Failed to load document'));
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
        });
}

// Helper function to handle common file not found errors
function handleFileNotFoundError(textContent, jsonFilename, changes) {
    console.log('Trying fallback methods for save_edits due to file not found');
    
    // Show retry indicator
    const retryIndicator = document.createElement('div');
    retryIndicator.className = 'save-indicator info';
    retryIndicator.textContent = 'Retrying with alternate method...';
    retryIndicator.style = 'opacity: 1;';
    textContent.appendChild(retryIndicator);
    
    // Try alternative filename patterns
    const fallbackFilenames = [
        'combined_with_spanning.json',
        jsonFilename.replace('_res_combined_with_spanning.json', '.json'),
        'results.json'
    ];
    
    // Try each fallback filename in sequence
    let currentIndex = 0;
    
    function tryNextFallback() {
        if (currentIndex >= fallbackFilenames.length) {
            // We've tried all fallbacks and failed
            retryIndicator.remove();
            showErrorMessage(textContent, 'Could not save changes: File not found');
            return;
        }
        
        const fallbackName = fallbackFilenames[currentIndex];
        console.log(`Trying fallback #${currentIndex + 1}: ${fallbackName}`);
        retryIndicator.textContent = `Retrying with ${fallbackName}...`;
        
        fetch('/save_edits/' + fallbackName, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(changes)
        })
        .then(response => {
            if (!response.ok) {
                // If this fallback fails, try the next one
                currentIndex++;
                return tryNextFallback();
            }
            return response.json();
        })
        .then(data => {
            if (data && data.success) {
                // Success!
                retryIndicator.remove();
                console.log('Fallback succeeded:', data);
                
                // Show success message
                const successIndicator = document.createElement('div');
                successIndicator.className = 'save-indicator success';
                successIndicator.textContent = 'Changes saved successfully';
                textContent.appendChild(successIndicator);
                
                // Fade out success message
                setTimeout(() => {
                    successIndicator.style.opacity = '0';
                    setTimeout(() => successIndicator.remove(), 1000);
                }, 2000);
            } else if (data) {
                // We got a response but it wasn't successful
                currentIndex++;
                tryNextFallback();
            }
        })
        .catch(error => {
            console.error('Error with fallback:', error);
            currentIndex++;
            tryNextFallback();
        });
    }
    
    // Start the fallback cascade
    tryNextFallback();
} 