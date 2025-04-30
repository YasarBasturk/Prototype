# Image Processing Pipeline

A web application that processes images through multiple stages to detect and extract text from documents.

## Features

- Image upload and preprocessing
- Text detection using PaddleOCR
- Cell detection for structured documents
- Text merging and splitting for complex layouts
- Editable results with confidence scores
- Results storage in SQLite database
- View and manage saved results

## Setup

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Initialize the database:

```bash
python Scripts/server.py
```

## Directory Structure

- `Scripts/`: Python processing scripts
  - `server.py`: Flask web server
  - `image_preprocess.py`: Image preprocessing
  - `ppstructure.py`: OCR processing
  - `cell_detection.py`: Table cell detection
  - `merge_split.py`: Text merging and splitting
- `Static/`: Static assets
  - `css/`: Stylesheets
  - `js/`: JavaScript files
- `template/`: HTML templates
- `uploads/`: Uploaded images
- `output/`: Processing results

## Usage

1. Start the server:

```bash
python Scripts/server.py
```

2. Open a web browser and navigate to:

```
http://localhost:5000
```

3. Upload an image and wait for processing to complete

4. Review and edit the detected text elements

5. Save the results with a custom name

## Processing Pipeline

    1. **Image Upload & Quality Assessment (IQA):** Receive image, check resolution, blur, brightness, and OCR confidence (EasyOCR). _(Only relevant for the mobile app path, not the main web app path)_
    2. **Preprocessing:** Enhance image quality (Dewarp, CLAHE, Gamma). _(Used by the web app path)_
    3. **Cell Detection:** Detect table cells (RT-DETR-L). _(Used by the web app path)_
    4. **AI Model (OCR):** Extract text and structure using PaddleOCR PP-Structure. _(Used by the web app path)_
    5. **Merge/Split:** Combine cell and OCR results, handle spanning text. _(Used by the web app path)_
    6. **Display/Edit:** Show results for review and editing. _(Web app)_
    7. **Save:** Store results in the database. _(Web app)_

## Technologies Used

- Flask: Web framework
- PaddleOCR: OCR engine
- OpenCV: Image processing
- SQLite: Data storage
- HTML/CSS/JavaScript: Frontend interface
