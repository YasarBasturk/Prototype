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

1. Image Upload: Save the original image
2. Preprocessing: Enhance image quality
3. OCR: Extract text using PaddleOCR
4. Cell Detection: Detect table cells
5. Merge/Split: Combine results and handle complex text layouts
6. Display: Show results for review and editing

## Technologies Used

- Flask: Web framework
- PaddleOCR: OCR engine
- OpenCV: Image processing
- SQLite: Data storage
- HTML/CSS/JavaScript: Frontend interface
