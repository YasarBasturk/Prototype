document.addEventListener('DOMContentLoaded', function() {
    const processImageForm = document.getElementById('processImageForm');
    const saveBtn = document.getElementById('saveBtn');
    const viewDocumentsBtn = document.getElementById('viewDocumentsBtn');
    const spinner = document.getElementById('spinner');
    const imageContainer = document.getElementById('imageContainer');
    const originalImageContainer = document.getElementById('originalImageContainer');
    const textResults = document.getElementById('textResults');
    const saveResult = document.getElementById('saveResult');
    const processResult = document.getElementById('processResult');
    
    // Bootstrap modals
    const documentsModal = new bootstrap.Modal(document.getElementById('documentsModal'));
    const documentDetailsModal = new bootstrap.Modal(document.getElementById('documentDetailsModal'));
    
    // Document viewer elements
    const documentsList = document.getElementById('documentsList');
    const documentInfo = document.getElementById('documentInfo');
    const documentImage = document.getElementById('documentImage');
    const documentTextItems = document.getElementById('documentTextItems');
    
    let ocrData = null;
    let editedItems = new Set();
    let currentDocumentId = null;
    
    // If template is available, show a message
    if (window.hasTemplate) {
        console.log('Template is loaded. Only non-template text will be editable.');
    }

    // Handle image processing form
    if (processImageForm) {
        processImageForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const imageFile = document.getElementById('imageFile').files[0];
            
            if (!imageFile) {
                alert('Image file is required');
                return;
            }
            
            const formData = new FormData();
            formData.append('image_file', imageFile);
            
            // Show loading spinner and processing message
            spinner.classList.remove('d-none');
            processResult.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Processing your image, please wait...</div>';
            
            // Clear previous data
            textResults.innerHTML = '<p class="text-muted">Processing image...</p>';
            imageContainer.innerHTML = '<p class="text-muted">Processing image...</p>';
            originalImageContainer.innerHTML = '<p class="text-muted">Processing image...</p>';
            
            fetch('/process_image', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || 'Server error: ' + response.status);
                    }).catch(() => {
                        // If we can't parse the JSON, just throw the HTTP error
                        throw new Error('Network response was not ok: ' + response.status);
                    });
                }
                return response.json();
            })
            .then(data => {
                // Hide spinner
                spinner.classList.add('d-none');
                
                // Even with a successful HTTP response, check if the data indicates an error
                if (!data.success) {
                    throw new Error(data.error || 'Unknown server error');
                }
                
                // Save OCR data and text spanning data
                if (!data.ocr_results || !Array.isArray(data.ocr_results)) {
                    throw new Error('Invalid OCR data received from server');
                }
                
                ocrData = data.ocr_results;
                
                // Store the processing data globally for other functions to access
                window.currentProcessingData = data;
                
                // Check for text spanning results
                if (data.text_spanning) {
                    console.log("Text spanning results found:", data.text_spanning);
                    
                    // Create container for text spanning results if it doesn't exist
                    let spanningContainer = document.getElementById('spanningResults');
                    if (!spanningContainer) {
                        spanningContainer = document.createElement('div');
                        spanningContainer.id = 'spanningResults';
                        spanningContainer.className = 'mt-4';
                        textResults.appendChild(spanningContainer);
                    }
                    
                    // Display text spanning results
                    let spanningHTML = '<h4>Text Spanning Results</h4>';
                    
                    // Display cells with text
                    if (data.text_spanning.cells_with_text && data.text_spanning.cells_with_text.length > 0) {
                        spanningHTML += '<div class="cells-with-text mt-3">';
                        spanningHTML += '<h5>Cells with Text</h5>';
                        
                        data.text_spanning.cells_with_text.forEach(cell => {
                            spanningHTML += `<div class="cell-item mb-3 p-2 border rounded">`;
                            spanningHTML += `<strong>Cell ID:</strong> ${cell.cell_id}<br>`;
                            spanningHTML += `<strong>Combined Text:</strong> ${cell.text}<br>`;
                            
                            // Display component texts (including split text)
                            if (cell.component_texts && cell.component_texts.length > 0) {
                                spanningHTML += '<div class="component-texts mt-2">';
                                cell.component_texts.forEach(comp => {
                                    if (comp.is_split) {
                                        spanningHTML += `<div class="split-text text-info">`;
                                        spanningHTML += `<strong>Split Part:</strong> ${comp.text}<br>`;
                                        spanningHTML += `<small>Original: ${comp.original_text}</small>`;
                                        spanningHTML += '</div>';
                                    } else {
                                        spanningHTML += `<div class="regular-text">`;
                                        spanningHTML += `<strong>Text:</strong> ${comp.text}`;
                                        spanningHTML += '</div>';
                                    }
                                });
                                spanningHTML += '</div>';
                            }
                            
                            spanningHTML += '</div>';
                        });
                        spanningHTML += '</div>';
                    }
                    
                    // Display spanning text assignments
                    if (data.text_spanning.spanning_text && data.text_spanning.spanning_text.length > 0) {
                        spanningHTML += '<div class="spanning-text mt-3">';
                        spanningHTML += '<h5>Text Spanning Multiple Cells</h5>';
                        
                        data.text_spanning.spanning_text.forEach(item => {
                            spanningHTML += `<div class="spanning-item mb-3 p-2 border rounded">`;
                            spanningHTML += `<strong>Original Text:</strong> ${item.text}<br>`;
                            spanningHTML += `<strong>Assigned to Cells:</strong> ${item.assigned_to_cells.join(', ')}<br>`;
                            spanningHTML += '<strong>Split Parts:</strong><br>';
                            item.split_texts.forEach(text => {
                                spanningHTML += `<div class="split-part ms-3">${text}</div>`;
                            });
                            spanningHTML += '</div>';
                        });
                        spanningHTML += '</div>';
                    }
                    
                    // Display metadata
                    if (data.text_spanning.metadata) {
                        spanningHTML += '<div class="spanning-metadata mt-3">';
                        spanningHTML += '<h5>Processing Statistics</h5>';
                        spanningHTML += `<p>
                            Total Cells: ${data.text_spanning.metadata.total_cells}<br>
                            Cells with Text: ${data.text_spanning.metadata.cells_with_text}<br>
                            Empty Cells: ${data.text_spanning.metadata.empty_cells}<br>
                            Total Text Items: ${data.text_spanning.metadata.total_text_items}<br>
                            Assigned Text Items: ${data.text_spanning.metadata.assigned_text_items}<br>
                            Unassigned Text: ${data.text_spanning.metadata.unassigned_text}<br>
                            Spanning Text Items: ${data.text_spanning.metadata.spanning_text_items}
                        </p>`;
                        spanningHTML += '</div>';
                    }
                    
                    spanningContainer.innerHTML = spanningHTML;
                } else {
                    console.log("No text spanning results found in the data");
                }
                
                // Display original image
                if (data.original_image) {
                    displayOriginalImage(data.original_image);
                }
                
                // Display spanning visualization if available
                if (data.spanning_image_base64) {
                    console.log("Using spanning visualization image");
                    displayAnnotatedImage(data.spanning_image_base64);
                    
                    // Add info about cell detection and text spanning
                    const infoElement = document.createElement('div');
                    infoElement.className = 'alert alert-info mt-3';
                    infoElement.innerHTML = `
                        <h5>Processing Results:</h5>
                        <p>✓ Cell Detection completed<br>
                           ✓ Text Spanning Analysis completed</p>
                    `;
                    imageContainer.appendChild(infoElement);
                } else {
                    console.log("No spanning visualization available, using standard OCR image");
                    if (data.image) {
                        displayAnnotatedImage(data.image);
                    } else {
                        console.log("No image data available");
                    }
                }
                
                // Display text results (only handwritten/editable text)
                displayTextResults(ocrData);
                
                // Enable save button
                saveBtn.disabled = false;
                
                // Show success message with information about applied techniques
                processResult.innerHTML = `<div class="alert alert-success">
                    <i class="bi bi-check-circle"></i> Image processed successfully!
                    <br>
                    <small>${ocrData.length} text elements detected</small>
                    ${data.spanning_applied ? 
                        `<br><small class="text-success"><strong>Text Spanning Applied</strong> - Text in table cells is properly identified</small>` : ''}
                    ${data.cell_detection_applied ? 
                        `<br><small class="text-success"><strong>Cell Detection Applied</strong> - Table structure detected</small>` : ''}
                </div>`;
            })
            .catch(error => {
                spinner.classList.add('d-none');
                console.error('Error:', error);
                processResult.innerHTML = `<div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Error processing image: ${error.message}
                </div>`;
                
                // Reset containers
                textResults.innerHTML = '<p class="text-muted">Upload an image to view and edit detected text</p>';
                imageContainer.innerHTML = '<p class="text-muted">Upload an image to see annotated results</p>';
                originalImageContainer.innerHTML = '<p class="text-muted">Upload an image to see it here</p>';
            });
        });
    }

    // Display original image
    function displayOriginalImage(base64Image) {
        if (!base64Image) {
            originalImageContainer.innerHTML = '<p class="text-danger">Unable to load original image</p>';
            return;
        }
        
        originalImageContainer.innerHTML = `
            <div class="img-container">
                <img src="data:image/jpeg;base64,${base64Image}" alt="Original Image" class="img-fluid">
                <div class="image-controls mt-2">
                    <div class="form-check form-switch">
                        <input class="form-check-input toggle-fit" type="checkbox" id="toggleOriginalFit" checked>
                        <label class="form-check-label" for="toggleOriginalFit">Fit to view</label>
                    </div>
                </div>
            </div>
        `;
        
        // Add toggle functionality
        const toggleFit = document.getElementById('toggleOriginalFit');
        if (toggleFit) {
            toggleFit.addEventListener('change', function() {
                const imgContainer = this.closest('.img-container');
                if (this.checked) {
                    imgContainer.classList.remove('actual-size');
                } else {
                    imgContainer.classList.add('actual-size');
                }
            });
        }
    }

    // Display annotated image
    function displayAnnotatedImage(base64Image) {
        if (!base64Image) {
            imageContainer.innerHTML = '<p class="text-danger">Unable to load annotated image</p>';
            return;
        }
        
        // Check if this is likely a spanning visualization (from parameters passed to this function)
        const isSpanningVisualization = window.currentProcessingData && 
                                       window.currentProcessingData.spanning_applied &&
                                       window.currentProcessingData.spanning_image_base64 === base64Image;
        
        // Create appropriate legend based on whether this is OCR or spanning visualization
        let legendHtml = '';
        
        if (isSpanningVisualization) {
            // Legend for spanning visualization
            legendHtml = `
                <div class="image-legend mt-3">
                    <h6>Text Spanning & Cell Detection Visualization</h6>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(0, 255, 0);"></span>
                        <span class="ms-2">Cells with text (green)</span>
                    </div>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(255, 0, 0);"></span>
                        <span class="ms-2">Empty cells (red)</span>
                    </div>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(255, 0, 255);"></span>
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
        } else {
            // Regular OCR visualization legend
            legendHtml = `
                <div class="image-legend mt-3">
                    <h6>OCR Text Detection</h6>
                    <div class="d-flex align-items-center mb-2">
                        <span class="legend-color-box" style="background-color: rgb(0, 255, 0);"></span>
                        <span class="ms-2">Editable text (handwritten, not in template)</span>
                    </div>
                    <div class="d-flex align-items-center">
                        <span class="legend-color-box" style="background-color: rgb(255, 0, 0);"></span>
                        <span class="ms-2">Non-editable text (printed, in template)</span>
                    </div>
                </div>
            `;
        }
        
        imageContainer.innerHTML = `
            <div class="img-container">
                <img src="data:image/jpeg;base64,${base64Image}" alt="Annotated Image" class="img-fluid">
                <div class="image-controls mt-2">
                    <div class="form-check form-switch">
                        <input class="form-check-input toggle-fit" type="checkbox" id="toggleAnnotatedFit" checked>
                        <label class="form-check-label" for="toggleAnnotatedFit">Fit to view</label>
                    </div>
                </div>
                ${legendHtml}
            </div>
        `;
        
        // Add toggle functionality
        const toggleFit = document.getElementById('toggleAnnotatedFit');
        if (toggleFit) {
            toggleFit.addEventListener('change', function() {
                const imgContainer = this.closest('.img-container');
                if (this.checked) {
                    imgContainer.classList.remove('actual-size');
                } else {
                    imgContainer.classList.add('actual-size');
                }
            });
        }
    }

    // Display text results with editing capability
    function displayTextResults(results) {
        if (!results || results.length === 0) {
            textResults.innerHTML = '<div class="no-results">No OCR results available</div>';
            return;
        }
        
        // Clean up results - ensure all items have valid text
        results.forEach(item => {
            if (!item.text || item.text === 'undefined' || item.text === 'NO_TEXT_DETECTED') {
                item.text = '';
                console.log('Fixed item with missing/undefined text:', item);
            }
        });
        
        // Filter out template items - only keep handwritten/editable items
        const editableItems = results.filter(item => {
            // Trust the server's handwritten flag without additional checks
            return item.handwritten === true;
        });
        
        // Log the filtering results for debugging
        console.log("All items:", results);
        console.log("Filtered editable items:", editableItems);
        
        // Count how many handwritten (editable) items we have
        const handwrittenCount = editableItems.length;
        
        console.log(`Total items: ${results.length}, Editable items: ${handwrittenCount}`);
        
        // If we have a template but no handwritten text, show a helpful message
        if (handwrittenCount === 0 && window.hasTemplate) {
            textResults.innerHTML = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle-fill"></i>
                    <strong>No editable text found.</strong> All detected text appears to be part of the template.
                    <br>
                    If you were expecting editable content, try one of these:
                    <ul>
                        <li>Adjust the template matching threshold in the backend</li>
                        <li>Check if the uploaded image has the same orientation as the template</li>
                        <li>Verify that the OCR has correctly detected handwritten content</li>
                    </ul>
                </div>
            `;
            return;
        }
        
        // Add filter controls and information
        let html = `
            <div class="mb-4">
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i> 
                    <strong>Template-Based Mode:</strong> 
                    ${window.hasTemplate ? 
                      'Only text that doesn\'t match the template is shown below and can be edited.' : 
                      'No template found. All text is displayed and can be toggled for editing.'}
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <h4>Editable Text Items (${handwrittenCount})</h4>
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="toggleEdited" ${editedItems.size > 0 ? 'checked' : ''}>
                        <label class="form-check-label" for="toggleEdited">Show only edited items</label>
                    </div>
                </div>
            </div>
            <div class="row" id="textItemsContainer">
        `;
        
        // Only display handwritten/editable items
        editableItems.forEach((item, i) => {
            // Get the original index from the full results array
            const index = results.indexOf(item);
            const isEdited = editedItems.has(index);
            const editedClass = isEdited ? 'text-item-edited' : '';
            
            html += `
                <div class="col-md-6 col-lg-4 text-item-container" 
                     data-edited="${isEdited}" 
                     data-index="${index}">
                    <div class="text-item text-item-handwritten ${editedClass}" data-index="${index}">
                        <div class="d-flex justify-content-between align-items-start">
                            <span class="text-index">Item #${index}</span>
                            <button class="btn btn-sm btn-primary btn-edit" data-index="${index}">Edit</button>
                        </div>
                        <div class="text-content mt-2">
                            <div class="text-type-badge badge-handwritten">
                                Editable
                            </div>
                            ${item.text || '<i>Empty text</i>'}
                        </div>
                        <div class="text-coords">Region: ${JSON.stringify(item.text_region)}</div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        textResults.innerHTML = html;
        
        // Add toggle functionality for edited items
        const toggleEditedCheck = document.getElementById('toggleEdited');
        if (toggleEditedCheck) {
            toggleEditedCheck.addEventListener('change', function() {
                filterEditedItems(this.checked);
            });
            
            // Initial state based on checkbox
            if (toggleEditedCheck.checked) {
                filterEditedItems(true);
            }
        }
        
        // Add event listeners to edit buttons
        document.querySelectorAll('.btn-edit').forEach(btn => {
            btn.addEventListener('click', function() {
                const index = parseInt(this.getAttribute('data-index'));
                
                // Get the text content element
                const textItem = document.querySelector(`.text-item[data-index="${index}"]`);
                const textContent = textItem.querySelector('.text-content');
                
                // Get the current text
                const currentText = results[index].text || '';
                
                // Replace content with textarea
                textContent.innerHTML = `
                    <div class="text-type-badge badge-handwritten">
                        Editable
                    </div>
                    <div class="edit-controls">
                        <textarea class="form-control edit-textarea" rows="3">${currentText}</textarea>
                        <div class="d-flex mt-2">
                            <button class="btn btn-sm btn-secondary me-2 cancel-edit">Cancel</button>
                            <button class="btn btn-sm btn-success save-edit" data-index="${index}">Save</button>
                        </div>
                    </div>
                `;
                
                // Add event listeners to cancel and save buttons
                const cancelBtn = textContent.querySelector('.cancel-edit');
                const saveBtn = textContent.querySelector('.save-edit');
                
                cancelBtn.addEventListener('click', function() {
                    textContent.innerHTML = `
                        <div class="text-type-badge badge-handwritten">
                            Editable
                        </div>
                        ${currentText || '<i>Empty text</i>'}
                    `;
                });
                
                saveBtn.addEventListener('click', function() {
                    const newText = textContent.querySelector('.edit-textarea').value;
                    
                    // Show spinner
                    spinner.classList.remove('d-none');
                    
                    // Send update to server
                    fetch('/update_text', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            index: index,
                            text: newText
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        // Hide spinner
                        spinner.classList.add('d-none');
                        
                        if (data.success) {
                            // Update local data
                            results[index].text = newText;
                            
                            // Update UI
                            textContent.innerHTML = `
                                <div class="text-type-badge badge-handwritten">
                                    Editable
                                </div>
                                ${newText || '<i>Empty text</i>'}
                            `;
                            
                            // Track edited items
                            editedItems.add(index);
                            
                            // Update container attribute for filtering
                            const container = document.querySelector(`.text-item-container[data-index="${index}"]`);
                            container.setAttribute('data-edited', 'true');
                            textItem.classList.add('text-item-edited');
                            
                            // Update image
                            if (data.image) {
                                displayAnnotatedImage(data.image);
                            }
                        } else {
                            alert(`Failed to update text: ${data.error || 'Unknown error'}`);
                            
                            // Restore original content
                            textContent.innerHTML = `
                                <div class="text-type-badge badge-handwritten">
                                    Editable
                                </div>
                                ${currentText || '<i>Empty text</i>'}
                            `;
                        }
                    })
                    .catch(error => {
                        spinner.classList.add('d-none');
                        console.error('Error:', error);
                        alert(`Error updating text: ${error.message}`);
                    });
                });
            });
        });
    }
    
    // Filter to show only edited items
    function filterEditedItems(showOnlyEdited) {
        const containers = document.querySelectorAll('.text-item-container');
        
        containers.forEach(container => {
            const isEdited = container.getAttribute('data-edited') === 'true';
            
            if (showOnlyEdited) {
                container.style.display = isEdited ? '' : 'none';
            } else {
                container.style.display = '';
            }
        });
    }
    
    // Handle save button
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            if (!ocrData) {
                alert('No OCR data to save');
                return;
            }
            
            // Get the document name from input field
            const documentNameInput = document.getElementById('documentName');
            const documentName = documentNameInput.value.trim();
            
            // Validate document name
            if (!documentName) {
                saveResult.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i> 
                        Please enter a document name.
                    </div>
                `;
                documentNameInput.focus();
                return;
            }
            
            // Check document name length and pattern
            const namePattern = /^[A-Za-z0-9 _\-\(\)\.]{3,50}$/;
            if (!namePattern.test(documentName)) {
                saveResult.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i> 
                        Document name must be 3-50 characters and can include letters, numbers, spaces, hyphens, underscores, periods, and parentheses.
                    </div>
                `;
                documentNameInput.focus();
                documentNameInput.select();
                return;
            }
            
            // Show spinner
            spinner.classList.remove('d-none');
            saveResult.innerHTML = '';
            
            // Send save request with document name
            fetch('/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_name: documentName
                })
            })
            .then(response => response.json())
            .then(data => {
                // Hide spinner
                spinner.classList.add('d-none');
                
                if (data.success) {
                    saveResult.innerHTML = `
                        <div class="alert alert-success">
                            <i class="bi bi-check-circle"></i> 
                            Document saved successfully!
                            <br>
                            <small>Name: ${data.document_name}</small>
                            <br>
                            <small>Document ID: ${data.database_id}</small>
                        </div>
                    `;
                    
                    // Clear the document name input for the next save
                    documentNameInput.value = '';
                    
                    // Keep the save button enabled in case they make more edits
                } else {
                    // Check if this is a duplicate name error
                    if (data.error && data.error.includes('already exists')) {
                        saveResult.innerHTML = `
                            <div class="alert alert-warning">
                                <i class="bi bi-exclamation-triangle"></i> 
                                ${data.error}
                            </div>
                        `;
                        
                        // Focus the input field to make it easier for the user to change it
                        documentNameInput.focus();
                        documentNameInput.select();
                    } else {
                        saveResult.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="bi bi-exclamation-triangle"></i> 
                                Failed to save data: ${data.error || 'Unknown error'}
                            </div>
                        `;
                    }
                }
            })
            .catch(error => {
                spinner.classList.add('d-none');
                console.error('Error:', error);
                saveResult.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i> 
                        Error saving data: ${error.message}
                    </div>
                `;
            });
        });
    }
    
    // Document Viewer Functionality
    if (viewDocumentsBtn) {
        viewDocumentsBtn.addEventListener('click', function() {
            loadDocumentsList();
            documentsModal.show();
        });
    }
    
    // Load the list of saved documents
    function loadDocumentsList() {
        documentsList.innerHTML = '<p class="text-center"><i class="bi bi-hourglass-split"></i> Loading documents...</p>';
        
        fetch('/documents')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch documents');
                }
                return response.json();
            })
            .then(data => {
                if (!data.success) {
                    throw new Error(data.error || 'Unknown error loading documents');
                }
                
                if (!data.documents || data.documents.length === 0) {
                    documentsList.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> No documents have been saved yet.</div>';
                    return;
                }
                
                // Display documents list
                let html = '<div class="list-group">';
                
                data.documents.forEach(doc => {
                    const createdDate = new Date(doc.created_at);
                    const formattedDate = createdDate.toLocaleString();
                    
                    html += `
                        <div class="document-item" data-document-id="${doc.id}">
                            <div class="d-flex justify-content-between">
                                <h5>${doc.document_name || 'Unnamed Document'}</h5>
                                <span class="document-text-count">${doc.text_items_count} text items</span>
                            </div>
                            <div class="document-date">Created: ${formattedDate}</div>
                            <div class="document-filename">File: ${doc.filename}</div>
                            <div class="actions">
                                <button class="btn btn-sm btn-primary view-document" data-document-id="${doc.id}">
                                    <i class="bi bi-eye"></i> View Details
                                </button>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                documentsList.innerHTML = html;
                
                // Add event listeners to view buttons
                document.querySelectorAll('.view-document').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const docId = this.getAttribute('data-document-id');
                        loadDocumentDetails(docId);
                    });
                });
                
                // Make entire document item clickable
                document.querySelectorAll('.document-item').forEach(item => {
                    item.addEventListener('click', function(e) {
                        // But not if they clicked a button inside it
                        if (!e.target.closest('button')) {
                            const docId = this.getAttribute('data-document-id');
                            loadDocumentDetails(docId);
                        }
                    });
                });
            })
            .catch(error => {
                console.error('Error:', error);
                documentsList.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i> 
                        Error loading documents: ${error.message}
                    </div>
                `;
            });
    }
    
    // Load document details
    function loadDocumentDetails(documentId) {
        currentDocumentId = documentId;
        
        // Close the documents list modal
        documentsModal.hide();
        
        // Show document details modal with loading state
        documentInfo.innerHTML = '<p class="text-center"><i class="bi bi-hourglass-split"></i> Loading document info...</p>';
        documentImage.innerHTML = '<p class="text-center"><i class="bi bi-hourglass-split"></i> Loading image...</p>';
        documentTextItems.innerHTML = '<p class="text-center"><i class="bi bi-hourglass-split"></i> Loading text items...</p>';
        
        documentDetailsModal.show();
        
        // Fetch document details
        fetch(`/documents/${documentId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch document details');
                }
                return response.json();
            })
            .then(data => {
                if (!data.success) {
                    throw new Error(data.error || 'Unknown error loading document details');
                }
                
                displayDocumentInfo(data.document);
                displayDocumentTextItems(data.text_items);
                
                // Try to load the image - this might require additional endpoint
                if (data.document.image_path) {
                    loadDocumentImage(data.document.image_path);
                } else {
                    documentImage.innerHTML = '<p class="text-center text-muted">No image available</p>';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                documentInfo.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i> 
                        Error loading document details: ${error.message}
                    </div>
                `;
                documentImage.innerHTML = '<p class="text-center text-muted">Failed to load image</p>';
                documentTextItems.innerHTML = '<p class="text-center text-muted">Failed to load text items</p>';
            });
    }
    
    // Display document metadata
    function displayDocumentInfo(document) {
        const createdDate = new Date(document.created_at);
        const formattedDate = createdDate.toLocaleString();
        
        let html = `
            <div class="document-metadata">
                <dl>
                    <dt>Document Name</dt>
                    <dd>${document.document_name || 'Unnamed Document'}</dd>
                    
                    <dt>Document ID</dt>
                    <dd>${document.id}</dd>
                    
                    <dt>Filename</dt>
                    <dd>${document.filename}</dd>
                    
                    <dt>Created At</dt>
                    <dd>${formattedDate}</dd>
                    
                    <dt>Text Items</dt>
                    <dd>${document.text_items_count}</dd>
                </dl>
            </div>
        `;
        
        documentInfo.innerHTML = html;
    }
    
    // Load and display the document's image 
    function loadDocumentImage(imagePath) {
        documentImage.innerHTML = '<p class="text-center"><i class="bi bi-hourglass-split"></i> Loading image...</p>';
        
        // Use our new endpoint to get the image
        fetch(`/documents/${currentDocumentId}/image`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch image');
                }
                return response.json();
            })
            .then(data => {
                if (!data.success) {
                    throw new Error(data.error || 'Unknown error loading image');
                }
                
                // Display the image
                documentImage.innerHTML = `
                    <div class="img-container">
                        <img src="data:image/jpeg;base64,${data.image_base64}" alt="Document Image" class="img-fluid">
                        <div class="image-controls mt-2">
                            <div class="form-check form-switch">
                                <input class="form-check-input toggle-fit" type="checkbox" id="toggleDocumentFit" checked>
                                <label class="form-check-label" for="toggleDocumentFit">Fit to view</label>
                            </div>
                        </div>
                        <div class="mt-2 text-muted small">
                            <i class="bi bi-info-circle"></i> Image path: ${data.image_path}
                        </div>
                    </div>
                `;
                
                // Add toggle functionality
                const toggleFit = document.getElementById('toggleDocumentFit');
                if (toggleFit) {
                    toggleFit.addEventListener('change', function() {
                        const imgContainer = this.closest('.img-container');
                        if (this.checked) {
                            imgContainer.classList.remove('actual-size');
                        } else {
                            imgContainer.classList.add('actual-size');
                        }
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                documentImage.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i> 
                        Could not load image: ${error.message}
                        <br>
                        <small>Path: ${imagePath}</small>
                    </div>
                `;
            });
    }
    
    // Display document text items
    function displayDocumentTextItems(textItems) {
        if (!textItems || textItems.length === 0) {
            documentTextItems.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> No text items found in this document.</div>';
            return;
        }
        
        let html = `
            <p class="mb-3">Total items: ${textItems.length}</p>
            <div class="document-text-items">
        `;
        
        textItems.forEach(item => {
            // Determine confidence level for styling
            let confidenceClass = 'medium';
            if (item.confidence >= 0.8) {
                confidenceClass = 'high';
            } else if (item.confidence < 0.5) {
                confidenceClass = 'low';
            }
            
            html += `
                <div class="document-text-item ${item.is_handwritten ? 'handwritten' : ''}">
                    <div class="item-text">${item.text || '<i>Empty text</i>'}</div>
                    <div class="item-meta">
                        <div>
                            <strong>Type:</strong> ${item.is_handwritten ? 'Handwritten (Editable)' : 'Printed (Non-editable)'}
                        </div>
                        <div>
                            <strong>Confidence:</strong> 
                            <span class="confidence ${confidenceClass}">
                                ${Math.round(item.confidence * 100)}%
                            </span>
                        </div>
                        <div><strong>Edited:</strong> ${item.edited ? 'Yes' : 'No'}</div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        documentTextItems.innerHTML = html;
    }
}); 