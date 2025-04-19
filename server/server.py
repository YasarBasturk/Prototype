from flask import Flask, request, jsonify, render_template, send_file
import os
from werkzeug.utils import secure_filename
import traceback
import sys

# Add the parent directory to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import Scripts
from Scripts.image_preprocess import preprocess_image
from Scripts.cell_processing import run_cell_detection
from Scripts.ai_processing import ai_processing

# Import local modules with proper package paths
from server.merge_split_processing import merge_split_processing

app = Flask(__name__, 
            static_folder='../Static',
            template_folder='../template')

# Configure upload folder and create necessary directories
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, 'output')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
)

# Create necessary directories
directories = [
    UPLOAD_FOLDER,
    os.path.join(OUTPUT_ROOT, 'preprocessed'),
    os.path.join(OUTPUT_ROOT, 'cell detection'),
    os.path.join(OUTPUT_ROOT, 'image-preprocessing'),
    os.path.join(OUTPUT_ROOT, 'merge and split')
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Ensured directory exists: {directory}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/output/<path:filename>')
def output_file(filename):
    """Serve any file from the output directory."""
    return send_file(os.path.join(OUTPUT_ROOT, filename))

@app.route("/process_image", methods=["POST"])
def process_image():
    try:
        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
            
        # Save the uploaded file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        
        # Get base name without extension
        base_name = os.path.splitext(filename)[0]
        processed_filename = f'processed_{filename}'
        
        # Step 1: Process the image
        preprocessed_path = os.path.join(OUTPUT_ROOT, 'preprocessed', processed_filename)
        preprocess_image(upload_path, preprocessed_path)
        
        # Step 2: Cell Detection
        cell_json_path = run_cell_detection(preprocessed_path)
        
        # Step 3: AI Model Processing
        ai_json_path = ai_processing(preprocessed_path)
        
        # Step 4: Merge and Split Processing
        merged_json_path, merged_viz_path = merge_split_processing(
            cell_json_path=cell_json_path,
            ocr_json_path=ai_json_path,
            preprocessed_image_path=preprocessed_path
        )
        
        if not merged_viz_path or not os.path.exists(merged_viz_path):
            return jsonify({'error': 'Failed to generate visualization'}), 500
        
        # Convert absolute paths to relative URLs
        def get_relative_path(abs_path):
            return os.path.relpath(abs_path, OUTPUT_ROOT) if abs_path else ''
        
        return jsonify({
            'status': 'success',
            'original_path': f'/uploads/{filename}',
            'output_image': f'/output/{get_relative_path(merged_viz_path)}',  # Main visualization output
        })
        
    except Exception as e:
        error_msg = f"Error processing image: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500
