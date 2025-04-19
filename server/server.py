from flask import Flask, request, jsonify, render_template, send_file
import os
import sqlite3
from werkzeug.utils import secure_filename
import json
from datetime import datetime
import traceback
import sys
from image_preprocess import preprocess_image

# Add the Scripts directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our processing scripts with error handling
try:
    from Scripts.ananinami import run_paddle_ocr
    from cell_detection import run_cell_detection
    from merge_split import process_document
    print("Successfully imported processing modules")
except ImportError as e:
    print(f"Error importing processing modules: {e}")
    traceback.print_exc()
    sys.exit(1)

app = Flask(__name__, 
            static_folder='../Static',
            template_folder='../template')

# Configure upload folder and create necessary directories
UPLOAD_FOLDER = os.path.abspath('../uploads')
OUTPUT_ROOT = os.path.abspath('../output')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
)

# Create necessary directories
directories = [
    UPLOAD_FOLDER,
    os.path.join(OUTPUT_ROOT, 'preprocessed'),
    os.path.join(OUTPUT_ROOT, 'ocr'),
    os.path.join(OUTPUT_ROOT, 'cell_detection'),
    os.path.join(OUTPUT_ROOT, 'final')
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Ensured directory exists: {directory}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    try:
        db_path = os.path.abspath('../results.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS processed_images
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      original_image TEXT NOT NULL,
                      processed_image TEXT NOT NULL,
                      json_data TEXT NOT NULL,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        print(f"Database initialized at: {db_path}")
    except Exception as e:
        print(f"Error initializing database: {e}")
        traceback.print_exc()
        sys.exit(1)

@app.route('/')
def index():
    return render_template('index.html')

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
        
        # Step 1: Process the image
        processed_image_path = image_processing(upload_path)
        
        # Step 2: Detect cells (to be implemented)
        # detected_cells = detect_cells(processed_image_path)
        
        # Step 3: Structure image (to be implemented)
        # structured_image = structure_image(processed_image_path)
        
        # Step 4: Merge and split (to be implemented)
        # final_result = merge_and_split(detected_cells, structured_image)
        
        # For now, return the processed image path
        return jsonify({
            'status': 'success',
            'processed_image': processed_image_path
        })
        
    except Exception as e:
        error_msg = f"Error processing image: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

def image_processing(image_path):
    """
    Process the uploaded image using preprocessing steps.
    
    Args:
        image_path (str): Path to the uploaded image
        
    Returns:
        str: Path to the processed image
    """
    try:
        # Create output directory for preprocessed images if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.dirname(image_path)), 'output', 'preprocessed')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output path for processed image
        filename = os.path.basename(image_path)
        output_path = os.path.join(output_dir, f'processed_{filename}')
        
        # Process the image using functions from image_preprocess.py
        processed_image = preprocess_image(image_path, output_path)
        
        return output_path
        
    except Exception as e:
        print(f"Error in image processing: {str(e)}")
        raise

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        # Check if the post request has the file part
        if 'file' not in request.files:
            print("Error: No file part in the request")
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            print("Error: No selected file")
            return jsonify({'error': 'No selected file'}), 400
        
        if not file:
            print("Error: File object is invalid")
            return jsonify({'error': 'Invalid file'}), 400
        
        if not allowed_file(file.filename):
            print(f"Error: File type not allowed for {file.filename}")
            return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        try:
            # Save original image
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_filename = f"{timestamp}_{filename}"
            original_path = os.path.join(app.config['UPLOAD_FOLDER'], base_filename)
            
            print(f"Attempting to save file to: {original_path}")
            file.save(original_path)
            
            if not os.path.exists(original_path):
                raise Exception(f"Failed to save file to {original_path}")
                
            print(f"Successfully saved original image to: {original_path}")
            file_size = os.path.getsize(original_path)
            print(f"File size: {file_size} bytes")
            
            # Step 2: Preprocess image
            preprocessed_path = os.path.join(OUTPUT_ROOT, 'preprocessed', base_filename)
            print(f"Preprocessing image...")
            preprocess_image(original_path, preprocessed_path)
            print(f"Preprocessed image saved to: {preprocessed_path}")
            
            # Step 3: Run PPStructure
            print(f"Running OCR...")
            ocr_result = run_paddle_ocr(preprocessed_path, os.path.join(OUTPUT_ROOT, 'ocr'))
            ocr_json_path = os.path.join(OUTPUT_ROOT, 'ocr', f"{base_filename.split('.')[0]}_res_0.json")
            print(f"OCR results saved to: {ocr_json_path}")
            
            # Step 4: Run Cell Detection
            print(f"Running cell detection...")
            cell_json_path, cell_vis_path = run_cell_detection(original_path)
            if not cell_json_path or not cell_vis_path:
                raise Exception("Cell detection failed to produce output files")
            print(f"Cell detection results saved to: {cell_json_path}")
            
            # Step 5: Merge and Split
            print(f"Merging results...")
            final_result = process_document(
                cell_json_path=cell_json_path,
                ocr_json_path=ocr_json_path,
                output_dir=os.path.join(OUTPUT_ROOT, 'final'),
                image_path=original_path
            )
            
            if not final_result or 'output_paths' not in final_result:
                raise Exception("Merge process failed to produce output files")
            
            # Get paths for UI
            final_image_path = final_result['output_paths']['visualization']
            final_json_path = final_result['output_paths']['json']
            
            # Verify files exist
            if not all(os.path.exists(p) for p in [final_image_path, final_json_path]):
                raise Exception("Some output files are missing")
                
            print(f"Final results saved to: {final_json_path}")
            print(f"Final visualization saved to: {final_image_path}")
            
            return jsonify({
                'status': 'success',
                'image_path': final_image_path,
                'json_path': final_json_path,
                'original_path': original_path
            })
            
        except Exception as e:
            # If we failed after saving the original file, try to clean it up
            if 'original_path' in locals() and os.path.exists(original_path):
                try:
                    os.remove(original_path)
                    print(f"Cleaned up original file after error: {original_path}")
                except:
                    pass
            error_msg = f"Error processing image: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return jsonify({'error': error_msg}), 500
            
    except Exception as e:
        error_msg = f"Error handling upload: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500
        
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/save', methods=['POST'])
def save_results():
    try:
        data = request.json
        name = data.get('name')
        original_path = data.get('original_path')
        processed_path = data.get('processed_path')
        json_data = data.get('json_data')
        
        if not all([name, original_path, processed_path, json_data]):
            return jsonify({'error': 'Missing required data'}), 400
            
        conn = sqlite3.connect('../results.db')
        c = conn.cursor()
        c.execute('''INSERT INTO processed_images 
                     (name, original_image, processed_image, json_data)
                     VALUES (?, ?, ?, ?)''',
                 (name, original_path, processed_path, json.dumps(json_data)))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        error_msg = f"Error saving results: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

@app.route('/api/results', methods=['GET'])
def get_results():
    try:
        conn = sqlite3.connect('../results.db')
        c = conn.cursor()
        c.execute('SELECT * FROM processed_images ORDER BY timestamp DESC')
        results = c.fetchall()
        conn.close()
        
        formatted_results = []
        for row in results:
            formatted_results.append({
                'id': row[0],
                'name': row[1],
                'original_image': row[2],
                'processed_image': row[3],
                'json_data': json.loads(row[4]),
                'timestamp': row[5]
            })
        
        return jsonify(formatted_results)
    except Exception as e:
        error_msg = f"Error retrieving results: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

@app.route('/api/image/<path:filename>')
def serve_image(filename):
    try:
        return send_file(filename, mimetype='image/jpeg')
    except Exception as e:
        error_msg = f"Error serving image: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    print("Initializing server...")
    init_db()
    print("Starting Flask server...")
    app.run(debug=True, port=5000)