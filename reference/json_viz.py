from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import json
import cv2
import numpy as np
import os
from base64 import b64encode
import datetime
import uuid
import sqlite3
from cell_detection import run_cell_detection
from text_spanning import process_document
from paddle_OCR_detection import run_paddle_ocr

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database setup functions
def get_db_connection():
    """Create a connection to the SQLite database"""
    conn = sqlite3.connect('ocr_results.db')
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def init_db():
    """Initialize the database with the required tables and apply migrations"""
    conn = get_db_connection()
    
    # Create documents table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS ocr_document (
        id TEXT PRIMARY KEY,
        document_name TEXT,
        filename TEXT,
        created_at TEXT,
        image_path TEXT,
        original_image_path TEXT
    )
    ''')
    
    # Create text items table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS ocr_text_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT,
        text TEXT,
        confidence REAL,
        is_handwritten INTEGER,
        text_region TEXT,
        edited INTEGER DEFAULT 0,
        FOREIGN KEY (document_id) REFERENCES ocr_document (id)
    )
    ''')
    
    # Check if document_name column exists, if not add it (migration)
    try:
        # First, check if the table exists and has data
        table_info = conn.execute("PRAGMA table_info(ocr_document)").fetchall()
        column_names = [column[1] for column in table_info]
        
        if 'document_name' not in column_names:
            print("Adding document_name column to ocr_document table (migration)")
            conn.execute("ALTER TABLE ocr_document ADD COLUMN document_name TEXT")
            # Set default value for existing records
            conn.execute("UPDATE ocr_document SET document_name = 'Unnamed Document'")
    except Exception as e:
        print(f"Error during migration: {e}")
    
    conn.commit()
    conn.close()
    print("Database initialized")

# Document and text item serialization functions
def document_to_dict(doc):
    """Convert a document row to a dictionary"""
    # Get text items count
    conn = get_db_connection()
    count = conn.execute(
        'SELECT COUNT(*) FROM ocr_text_item WHERE document_id = ?', 
        (doc['id'],)
    ).fetchone()[0]
    conn.close()
    
    return {
        'id': doc['id'],
        'document_name': doc['document_name'] if 'document_name' in doc.keys() else 'Unnamed Document',
        'filename': doc['filename'],
        'created_at': doc['created_at'],
        'image_path': doc['image_path'],
        'original_image_path': doc['original_image_path'],
        'text_items_count': count
    }

def text_item_to_dict(item):
    """Convert a text item row to a dictionary"""
    return {
        'id': item['id'],
        'text': item['text'],
        'confidence': item['confidence'],
        'is_handwritten': bool(item['is_handwritten']),
        'text_region': json.loads(item['text_region']) if item['text_region'] else [],
        'edited': bool(item['edited'])
    }

# Store the current state
class State:
    def __init__(self):
        self.ocr_results = None
        self.image_path = None
        self.json_path = None
        self.template = None
        self.original_image_path = None

state = State()

# Load template from the provided JSON file
def load_template(session_id=None):
    """
    Load the template from the specified JSON file.
    The template contains all the fixed text elements that should not be editable.
    
    Args:
        session_id (str, optional): If provided, look for a template specific to this session
    """
    if session_id:
        # First try to find a session-specific template
        session_paths = [
            f'output/paddle-ocr-detection/result_{session_id}/res_0.json',
            f'output/paddle-ocr-detection/template_{session_id}.json',
            f'output/template_{session_id}.json'
        ]
        
        for path in session_paths:
            if os.path.exists(path):
                print(f"Loading session-specific template from: {path}")
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('res', data)  # Handle both structures
    
    # If no session-specific template or no session_id provided, try default templates
    default_paths = [
        'output/paddle-ocr-detection/IMG_5069_template/res_0.json',
        'output/res_0.json',
        'res_0.json',
        'template.json'
    ]
    
    for path in default_paths:
        if os.path.exists(path):
            print(f"Loading default template from: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('res', data)  # Handle both structures
    
    print("No template file found. All text will be considered editable.")
    return None

def load_json(json_path):
    """
    Load OCR results from a JSON file.
    Handles different possible structures of the JSON data.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if 'res' in data:
        results = data['res']
        
        # Check if results contains a single figure with nested text items
        if (len(results) == 1 and 
            isinstance(results[0], dict) and 
            'type' in results[0] and 
            results[0]['type'] == 'figure' and 
            'res' in results[0]):
            
            print(f"Found nested structure with {len(results[0]['res'])} text items")
            return results[0]['res']  # Return the actual text items directly
        
        # Standard format with a 'res' key
        return results
    elif isinstance(data, list):
        # Direct list of results
        return data
    elif isinstance(data, dict) and any(isinstance(val, list) for val in data.values()):
        # Find the first list value in the dictionary
        for key, value in data.items():
            if isinstance(value, list):
                print(f"Using list from key '{key}' in JSON data")
                return value
    
    # If we can't determine the structure, return the whole data
    print("Warning: Unrecognized JSON structure. Returning full data.")
    return data

def get_region_center(region):
    """Calculate the center point of a text region"""
    x_coords = [point[0] for point in region]
    y_coords = [point[1] for point in region]
    center_x = sum(x_coords) / len(x_coords)
    center_y = sum(y_coords) / len(y_coords)
    return center_x, center_y

def get_region_area(region):
    """Calculate the approximate area of a text region"""
    # Convert region to numpy array
    region_np = np.array(region, dtype=np.float32)
    # Calculate area using OpenCV
    area = cv2.contourArea(region_np)
    return area

def is_template_text(text_item, template):
    """
    Determine if a text item is part of the template (printed text)
    by comparing its position, size and content with template items.
    Uses a more sophisticated matching algorithm.
    """
    if not template:
        return False
    
    try:
        # Get the center and area of the current item
        if 'text_region' not in text_item:
            print(f"Warning: Item missing text_region: {text_item}")
            return False
            
        region = text_item['text_region']
        try:
            item_x, item_y = get_region_center(region)
            item_area = get_region_area(region)
        except Exception as e:
            print(f"Error calculating region metrics: {e} for region {region}")
            return False
            
        item_text = text_item.get('text', '').lower().strip()
        
        # Threshold for position matching - make it very strict
        position_threshold = 10  # pixels - reduced from 20 for even stricter matching
        
        # Threshold for area matching (as a percentage)
        area_threshold = 0.9  # 90% - increased from 80% for even stricter matching
        
        # Debug information
        print(f"Checking if '{item_text}' is template text")
        
        # Text-based direct matching for common form fields
        # This helps identify standard form fields that are part of templates
        common_template_texts = [
            'nasc', 'dt', 'dtp', 'nome', 'cpf', 'rg', 'cnpj', 'data', 'assinatura',
            'endereco', 'telefone', 'email', 'cidade', 'estado', 'cep', 'bairro',
            'rua', 'nascimento', 'mes', 'dia', 'ano', 'días', 'meses', 'años',
            'endereço', 'identidade', 'profissão', 'profissao', 'nacionalidade',
            # Adding specific items from the screenshot
            'dias', 'meses', 'nacer', 'dtp.', 'vas', 'hepb', 'bcg',
            # Adding vaccination-specific terms from recent screenshot
            'hib', 'vpo', 'rota', 'nunca', 'administrar', 'depois', 'semanas', 'vida',
            'ao', 'de'
        ]
        
        # If the text exactly matches a common template field, consider it part of the template
        if item_text.lower() in common_template_texts:
            print(f"Text '{item_text}' matches common template field")
            return True
        
        # Check if this item matches any template item
        for template_item in template:
            if 'text_region' not in template_item:
                continue
                
            try:
                template_region = template_item['text_region']
                template_x, template_y = get_region_center(template_region)
                template_area = get_region_area(template_region)
                template_text = template_item.get('text', '').lower().strip()
            except Exception as e:
                print(f"Error processing template item: {e}")
                continue
            
            # Calculate distance between centers
            distance = np.sqrt((item_x - template_x)**2 + (item_y - template_y)**2)
            
            # Calculate area difference ratio
            if template_area > 0 and item_area > 0:
                area_ratio = min(template_area, item_area) / max(template_area, item_area)
            else:
                area_ratio = 0
            
            # Text similarity calculation
            text_similarity = 0
            if item_text and template_text:
                # Exact match
                if item_text == template_text:
                    text_similarity = 1.0
                    print(f"Exact text match for '{item_text}' vs '{template_text}'")
                    return True
                # Contain match
                elif item_text in template_text or template_text in item_text:
                    text_similarity = len(min(item_text, template_text, key=len)) / len(max(item_text, template_text, key=len))
            
            # Debug information
            print(f"Comparing: '{item_text}' vs '{template_text}': distance={distance:.2f}, area_ratio={area_ratio:.2f}, text_similarity={text_similarity:.2f}")
                
            # Position is the primary matching factor
            if distance < position_threshold:
                print(f"Position match (within {position_threshold}px) for '{item_text}': {distance:.2f}")
                return True
                
            # If position is close and area is similar, it's likely a match
            if distance < 30 and area_ratio > area_threshold:
                print(f"Combined position and area match for '{item_text}': distance={distance:.2f}, area_ratio={area_ratio:.2f}")
                return True
            
            # Text similarity can be a strong indicator
            if text_similarity > 0.9:  # Increased from 0.8 for stricter matching
                print(f"Strong text similarity match for '{item_text}': {text_similarity:.2f}")
                return True
        
        # Check for specific vaccine patterns
        vaccine_patterns = [
            "hib", "vpo", "rota", "bcg", "dtp", "vas", "hepb", "penta"
        ]
        
        for pattern in vaccine_patterns:
            # Look for exact vaccine names or vaccine names followed by numbers/symbols
            if (pattern == item_text or 
                item_text.startswith(pattern + " ") or 
                item_text.startswith(pattern + "-") or
                item_text.startswith(pattern + "*") or
                any(item_text.startswith(f"{pattern}{num}") for num in ["1", "2", "3", "4", "5"])):
                print(f"Text '{item_text}' contains vaccine pattern '{pattern}' - marking as template")
                return True
        
        # Check for formats like "VPO 2" or "ROTA-2*"
        if (any(f"{p} " in item_text for p in vaccine_patterns) or
            any(f"{p}-" in item_text for p in vaccine_patterns)):
            print(f"Text '{item_text}' matches vaccine with dose format - marking as template")
            return True
        
        # Special case for the warning text
        if ("nunca" in item_text or "administrar" in item_text or 
            "semanas" in item_text or "depois" in item_text or "vida" in item_text):
            print(f"Text '{item_text}' appears to be a medical instruction - marking as template")
            return True
        
        return False
    except Exception as e:
        print(f"Error in is_template_text: {e} for item: {text_item}")
        return False  # In case of any error, don't consider it a template item

def identify_handwritten_text(ocr_results, template):
    """
    Identify which text items are handwritten based on template comparison.
    If an item is in the template, it's considered printed; otherwise, it's handwritten.
    """
    if ocr_results is None:
        print("Warning: ocr_results is None")
        return []
        
    print(f"Processing OCR results with {len(ocr_results)} items")
    
    # First, handle nested structure - if the results contain a figure with a 'res' array
    if len(ocr_results) == 1 and isinstance(ocr_results[0], dict):
        if 'type' in ocr_results[0] and ocr_results[0]['type'] == 'figure' and 'res' in ocr_results[0]:
            print(f"Found nested structure with figure type, extracting inner results ({len(ocr_results[0]['res'])} items)")
            inner_results = ocr_results[0]['res']
            # Process these inner results recursively
            processed_results = identify_handwritten_text(inner_results, template)
            return processed_results

    # Make a deep copy to avoid modifying the original data
    for item in ocr_results:
        # Start with all items as potentially handwritten
        item['handwritten'] = True
        
        # Ensure text field exists and is not undefined/empty
        if 'text' not in item or item['text'] is None:
            item['text'] = "NO_TEXT_DETECTED"
            print(f"Warning: Item without text field: {item}")
        
        # Check if the item has a text_region (required for template matching)
        if 'text_region' not in item:
            # If this is from PaddleOCR, it might use 'box' or 'bbox' instead
            if 'box' in item:
                # Convert box format to text_region format
                item['text_region'] = item['box']
                print(f"Converted 'box' to 'text_region' for item: {item.get('text', '')}")
            elif 'bbox' in item:
                # Convert bbox format [x, y, width, height] to text_region format
                x, y, w, h = item['bbox']
                item['text_region'] = [[x, y], [x+w, y], [x+w, y+h], [x, y+h]]
                print(f"Converted 'bbox' to 'text_region' for item: {item.get('text', '')}")
            else:
                # Skip this item for template matching
                print(f"Warning: Item without text_region, box, or bbox cannot be matched against template: {item}")
                continue
    
    # If we have a template, use it to identify non-editable items
    if template:
        print(f"Using template with {len(template)} items to identify non-editable text")
        
        # Count how many items are marked as handwritten before and after template matching
        handwritten_before = sum(1 for item in ocr_results if item.get('handwritten', True))
        
        for i, item in enumerate(ocr_results):
            # Skip items without text_region (can't be matched to template)
            if 'text_region' not in item:
                continue
                
            # Check if this text is part of the template
            if is_template_text(item, template):
                # Mark template matches as non-handwritten (non-editable)
                ocr_results[i]['handwritten'] = False
                print(f"Marked as template (non-editable): {item.get('text', '')}")
            else:
                # Items not in template are considered handwritten/editable
                ocr_results[i]['handwritten'] = True
                print(f"Marked as handwritten (editable): {item.get('text', '')}")
        
        # Count how many items are marked as handwritten after template matching
        handwritten_after = sum(1 for item in ocr_results if item.get('handwritten', True))
        print(f"Handwritten items before/after template matching: {handwritten_before}/{handwritten_after}")
    else:
        print("No template available, all items will be considered handwritten/editable")
    
    return ocr_results

def validate_image_path(image_path):
    """Validate that an image path exists and is readable by OpenCV"""
    if not image_path:
        print("Warning: Image path is None or empty")
        return False
        
    if not os.path.exists(image_path):
        print(f"Warning: Image path does not exist: {image_path}")
        return False
        
    # Try to read the image with OpenCV
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"Warning: OpenCV could not read image at: {image_path}")
            return False
        
        # Image is valid
        print(f"Image validated: {image_path} ({img.shape[1]}x{img.shape[0]})")
        return True
    except Exception as e:
        print(f"Error validating image: {e}")
        return False

def get_annotated_image():
    if state.image_path is None or state.ocr_results is None:
        print("Warning: Cannot generate image - image_path or ocr_results is None")
        return None
    
    # First check if we have a text_spanning visualization
    # Look in both possible combined_results directories
    combined_dirs = ['combined_results', 'output/combined_results']
    
    for combined_dir in combined_dirs:
        if os.path.exists(combined_dir):
            # Try with original image name first
            if state.original_image_path:
                base_name = os.path.basename(state.original_image_path).split('.')[0]
                # This is the expected path pattern for text_spanning visualization
                potential_vis_path = os.path.join(combined_dir, f"{base_name}_visualization_with_spanning.jpg")
                
                # Also try with just "IMG_" prefix
                if not os.path.exists(potential_vis_path):
                    potential_vis_path = os.path.join(combined_dir, "IMG_visualization_with_spanning.jpg")
                
                # Check if visualization exists
                if os.path.exists(potential_vis_path):
                    print(f"Found text_spanning visualization: {potential_vis_path}")
                    try:
                        # Load and use the text_spanning visualization directly
                        img = cv2.imread(potential_vis_path)
                        if img is not None:
                            print(f"Successfully loaded text_spanning visualization")
                            _, buffer = cv2.imencode('.jpg', img)
                            img_base64 = b64encode(buffer).decode('utf-8')
                            return img_base64
                    except Exception as e:
                        print(f"Error loading text_spanning visualization: {e}, falling back to other options")
    
    # Validate image path
    if not validate_image_path(state.image_path):
        print(f"Trying to find alternative image file")
        # Try to find an alternative image
        base_name = os.path.basename(state.image_path).split('.')[0]
        alt_paths = [
            # Check in both combined_results dirs
            os.path.join('combined_results', f"{base_name}_visualization_with_spanning.jpg"),
            os.path.join('combined_results', "IMG_visualization_with_spanning.jpg"),
            os.path.join('output/combined_results', f"{base_name}_visualization_with_spanning.jpg"),
            # Check in cell detection dir
            os.path.join('output/cell detection', f"{base_name}.jpg"),
            # Check in preprocessed dir
            os.path.join('preprocessed', f"{base_name}.jpg"),
            # Check original image
            state.original_image_path
        ]
        
        for alt_path in alt_paths:
            if validate_image_path(alt_path):
                state.image_path = alt_path
                break
        else:
            print("Could not find any valid alternative image path")
            return None
    
    # Check if we have a path to a visualization from text_spanning
    base_name = os.path.basename(state.image_path)
    if 'visualization_with_spanning' in base_name and os.path.exists(state.image_path):
        print(f"Using existing visualization image: {state.image_path}")
        try:
            # Load and return the existing visualization without any additional annotations
            img = cv2.imread(state.image_path)
            if img is None:
                print(f"Warning: Failed to load visualization image at {state.image_path}, falling back to raw image")
            else:
                # Convert to base64 for web display
                _, buffer = cv2.imencode('.jpg', img)
                img_base64 = b64encode(buffer).decode('utf-8')
                return img_base64
        except Exception as e:
            print(f"Error loading visualization image: {e}, falling back to raw image")
    
    # If we get here, either there's no spanning visualization or it failed to load
    # So we'll return the raw image without annotations
    print(f"Returning raw image from: {state.image_path}")
    try:
        img = cv2.imread(state.image_path)
        if img is None:
            print(f"Error: Failed to load image at {state.image_path}")
            return None
        
        # Convert to base64 for web display without any annotations
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = b64encode(buffer).decode('utf-8')
        return img_base64
    except Exception as e:
        print(f"Error loading image: {e}")
        return None

@app.route('/')
def index():
    # Load template on server start
    if state.template is None:
        state.template = load_template()
    return render_template('index.html', has_template=(state.template is not None))

@app.route("/process_image", methods=["POST"])
def process_image(uploaded_image):
    """
    processed_image = image_processing(uploaded_image)
    detected_cells = detect_cells(processed_image) # returns a list of cells. Note using PaddleX
    structured_image = structure_image(processed_image) # returns ONE image with text regions and the text iself etc. Note using PPStructure
    merge_and_split(detected_cells, structured_image) # create a json file with some kinda of data that can be used by endpoints that retrieves data. For instance, an endpoint called /get-processed-image that returns data that can be used for showing the client relevant data.

    """

@app.route('/load_data', methods=['POST'])
def load_data():
    """
    Load data from uploaded JSON and image files.
    For consistency, this now redirects to the full process_image pipeline
    when image files are provided.
    """
    json_file = request.files.get('json_file')
    image_file = request.files.get('image_file')
    
    # If both files are provided, this is a direct upload of pre-processed results
    if json_file and image_file:
        # For backward compatibility, handle direct JSON+image upload
        json_path = 'uploads/temp.json'
        image_path = 'uploads/temp.jpg'
        os.makedirs('uploads', exist_ok=True)
        
        json_file.save(json_path)
        image_file.save(image_path)
        
        # Load data
        state.json_path = json_path
        state.image_path = image_path
        state.original_image_path = image_path  # Set original path
        state.ocr_results = load_json(json_path)
        
        # Load template if not already loaded
        if state.template is None:
            state.template = load_template()
        
        # Identify handwritten text based on template
        state.ocr_results = identify_handwritten_text(state.ocr_results, state.template)
        
        # Get annotated image
        img_base64 = get_annotated_image()
        
        return jsonify({
            'ocr_results': state.ocr_results,
            'image': img_base64,
            'has_template': state.template is not None
        })
    elif image_file:
        # If only image file is provided, redirect to the full processing pipeline
        return process_image()
    else:
        return jsonify({'error': 'At least an image file is required'}), 400

@app.route('/update_text', methods=['POST'])
def update_text():
    data = request.json
    idx = data.get('index')
    new_text = data.get('text')
    
    if idx is None or new_text is None:
        return jsonify({'error': 'Invalid request'}), 400
    
    # Only allow editing of handwritten text
    if not state.ocr_results[idx].get('handwritten', False):
        return jsonify({'error': 'Only handwritten text can be edited'}), 403
    
    # Update the text in the OCR results
    old_text = state.ocr_results[idx].get('text', '')
    state.ocr_results[idx]['text'] = new_text
    
    # Check if this text belongs to a cell
    cell_id = state.ocr_results[idx].get('cell_id', -1)
    if cell_id >= 0:
        print(f"Updating text in cell {cell_id} from '{old_text}' to '{new_text}'")
        
        # If we're in a spanning text situation, find other related pieces with the same cell_id
        # that might need to be updated in a coordinated way
        # This would be a more complex task requiring cell context, but we leave it simple
        
    # Get updated image
    img_base64 = get_annotated_image()
    
    return jsonify({
        'success': True,
        'image': img_base64,
        'cell_id': cell_id if cell_id >= 0 else None
    })

@app.route('/toggle_handwritten', methods=['POST'])
def toggle_handwritten():
    data = request.json
    idx = data.get('index')
    
    if idx is None:
        return jsonify({'error': 'Invalid request'}), 400
    
    # Toggle the handwritten flag
    state.ocr_results[idx]['handwritten'] = not state.ocr_results[idx].get('handwritten', False)
    
    # Get updated image
    img_base64 = get_annotated_image()
    
    return jsonify({
        'success': True,
        'is_handwritten': state.ocr_results[idx]['handwritten'],
        'image': img_base64
    })

@app.route('/save', methods=['POST'])
def save():
    if state.ocr_results is None:
        return jsonify({'error': 'No data to save'}), 400
    
    try:
        # Get document name from request if provided
        data = request.json or {}
        document_name = data.get('document_name', 'Unnamed Document')
        
        # Check if a document with this name already exists
        conn = get_db_connection()
        existing_doc = conn.execute(
            'SELECT id FROM ocr_document WHERE document_name = ?', 
            (document_name,)
        ).fetchone()
        
        if existing_doc:
            conn.close()
            return jsonify({
                'success': False,
                'error': f"A document with the name '{document_name}' already exists. Please choose a different name."
            }), 400
        
        # Generate a unique ID for the document
        document_id = str(uuid.uuid4())
        filename = os.path.basename(state.original_image_path) if state.original_image_path else "unknown.jpg"
        current_time = datetime.datetime.utcnow().isoformat()
        
        # Insert document record with custom name
        conn.execute(
            'INSERT INTO ocr_document (id, document_name, filename, created_at, image_path, original_image_path) VALUES (?, ?, ?, ?, ?, ?)',
            (document_id, document_name, filename, current_time, state.image_path, state.original_image_path)
        )
        
        # Insert text items
        for item in state.ocr_results:
            # Convert text_region to a JSON string for storage
            text_region_str = json.dumps(item.get('text_region', []))
            
            conn.execute(
                'INSERT INTO ocr_text_item (document_id, text, confidence, is_handwritten, text_region) VALUES (?, ?, ?, ?, ?)',
                (
                    document_id,
                    item.get('text', ''),
                    item.get('confidence', 0.0),
                    1 if item.get('handwritten', True) else 0,  # SQLite uses 0/1 for booleans
                    text_region_str
                )
            )
        
        # Commit the transaction
        conn.commit()
        conn.close()
        
        # Also save to a JSON file as before for backward compatibility
        output_path = 'output/corrected.json'
        os.makedirs('output', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'res': state.ocr_results}, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True, 
            'path': output_path,
            'database_id': document_id,
            'document_name': document_name
        })
    except Exception as e:
        print(f"Error saving to database: {str(e)}")
        
        return jsonify({
            'success': False,
            'error': f"Failed to save data: {str(e)}"
        }), 500

# Add a new endpoint to retrieve saved documents
@app.route('/documents', methods=['GET'])
def get_documents():
    try:
        conn = get_db_connection()
        docs = conn.execute('SELECT * FROM ocr_document ORDER BY created_at DESC').fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'documents': [document_to_dict(doc) for doc in docs]
        })
    except Exception as e:
        print(f"Error retrieving documents: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to retrieve documents: {str(e)}"
        }), 500

# Add endpoint to retrieve a specific document with its text items
@app.route('/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    try:
        conn = get_db_connection()
        doc = conn.execute('SELECT * FROM ocr_document WHERE id = ?', (document_id,)).fetchone()
        
        if not doc:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        # Get all text items for this document
        text_items = conn.execute(
            'SELECT * FROM ocr_text_item WHERE document_id = ?', 
            (document_id,)
        ).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'document': document_to_dict(doc),
            'text_items': [text_item_to_dict(item) for item in text_items]
        })
    except Exception as e:
        print(f"Error retrieving document: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to retrieve document: {str(e)}"
        }), 500

@app.route('/create_template', methods=['POST'])
def create_template():
    """
    Create a template from an uploaded JSON file.
    This sets all current OCR results as the template (non-editable).
    """
    json_file = request.files.get('json_file')
    
    if not json_file:
        return jsonify({'error': 'JSON file is required for template creation'}), 400
    
    # Generate a unique session ID for this template
    session_id = str(uuid.uuid4())[:8]
    
    # Create template directory with session ID
    template_dir = f'output/paddle-ocr-detection/template_{session_id}'
    os.makedirs(template_dir, exist_ok=True)
    template_path = os.path.join(template_dir, 'res_0.json')
    
    json_file.save(template_path)
    
    # Reload the template with the new session ID
    state.template = load_template(session_id)
    
    return jsonify({
        'success': True,
        'message': 'Template created successfully',
        'has_template': state.template is not None,
        'template_id': session_id
    })

class ProcessingState:
    """
    Class to manage the state of image processing, including file paths and results.
    """
    def __init__(self, image_path, session_id=None):
        self.original_image_path = image_path
        self.session_id = session_id or str(uuid.uuid4())
        
        # Initialize paths
        self.image_path = None
        self.json_path = None
        self.ocr_results = None
        
        # Load template
        self.template = load_template(self.session_id)
        print(f"Template loaded in ProcessingState: {self.template is not None}")
        
        # Cell detection paths
        self.cell_detection_json_path = os.path.join(
            'output', 'cell detection', 
            f'result_{self.session_id}', 'res_0.json'
        )
        
        # OCR paths
        self.ocr_json_path = os.path.join(
            'output', 'paddle-ocr-detection',
            f'result_{self.session_id}', 'res_0.json'
        )
        
        # Text spanning paths
        self.spanning_json_path = os.path.join(
            'output', 'combined_results',
            f'result_{self.session_id}', 'combined_with_spanning.json'
        )
        self.spanning_viz_path = os.path.join(
            'output', 'combined_results',
            f'result_{self.session_id}', 'visualization_with_spanning.jpg'
        )
        
        # Create necessary directories
        os.makedirs(os.path.dirname(self.cell_detection_json_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.ocr_json_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.spanning_json_path), exist_ok=True)

def process_image(image_path, session_id=None):
    """
    Process an image through the complete pipeline including text spanning.
    
    Args:
        image_path (str): Path to the input image
        session_id (str): Optional session ID for unique file naming
        
    Returns:
        dict: Processing results including paths to output files
    """
    try:
        # Step 1: Initialize state and create session directory
        state = ProcessingState(image_path, session_id)
        print(f"Processing image: {image_path}")
        print(f"Session ID: {session_id}")
        
        # Step 2: Run cell detection
        try:
            print("Running cell detection...")
            # Get the paths from cell detection
            cell_json_path, cell_viz_path = run_cell_detection(
                state.original_image_path,
                os.path.dirname(state.cell_detection_json_path)
            )
            
            if not cell_json_path or not cell_viz_path:
                raise Exception("Cell detection failed to produce output files")
                
            # Update state with cell detection paths
            state.cell_detection_json_path = cell_json_path
            state.cell_detection_viz_path = cell_viz_path
            
            # Load the cell detection results
            with open(cell_json_path, 'r', encoding='utf-8') as f:
                cell_detection_results = json.load(f)
                
            print(f"Cell detection complete: {len(cell_detection_results.get('boxes', []))} cells found")
        except Exception as e:
            print(f"Error in cell detection: {e}")
            return {"error": "Cell detection failed"}
        
        # Step 3: Run OCR
        try:
            print("Running OCR...")
            # Pass the image path and output directory as positional arguments
            ocr_results = run_paddle_ocr(
                state.original_image_path,
                os.path.dirname(state.ocr_json_path)
            )
            if not ocr_results:
                raise Exception("OCR failed")
            print(f"OCR complete: {len(ocr_results)} text regions found")
            
            # Ensure each text region has the required fields and proper format
            processed_ocr_results = []
            for item in ocr_results:
                # Handle both direct text items and nested results
                if isinstance(item, dict) and 'res' in item:
                    # Extract items from nested 'res' field
                    for subitem in item['res']:
                        processed_item = {
                            'text': subitem.get('text', ''),
                            'confidence': subitem.get('confidence', 0.0),
                            'text_region': subitem.get('text_region', subitem.get('box', [])),
                            'handwritten': True  # Will be updated by template matching later
                        }
                        processed_ocr_results.append(processed_item)
                else:
                    # Direct text item
                    processed_item = {
                        'text': item.get('text', ''),
                        'confidence': item.get('confidence', 0.0),
                        'text_region': item.get('text_region', item.get('box', [])),
                        'handwritten': True  # Will be updated by template matching later
                    }
                    processed_ocr_results.append(processed_item)
            
            # Update OCR results with processed version
            ocr_results = processed_ocr_results
            print(f"Processed {len(ocr_results)} text items")
            
            # Load and apply template matching
            print("Loading template for matching...")
            template = load_template(session_id)
            if template:
                print(f"Template loaded with {len(template)} items")
                # Apply template matching to identify handwritten vs printed text
                ocr_results = identify_handwritten_text(ocr_results, template)
                print("Template matching completed")
            else:
                print("No template found - all text will be considered handwritten")
                    
            # Save OCR results to JSON file
            with open(state.ocr_json_path, 'w', encoding='utf-8') as f:
                json.dump({'res': ocr_results}, f, ensure_ascii=False, indent=4)
                
        except Exception as e:
            print(f"Error in OCR: {e}")
            return {"error": "OCR failed"}
        
        # Step 4: Run text spanning
        try:
            print("Running text spanning...")
            # Create session-specific combined results directory
            combined_results_dir = os.path.join("output", "combined_results", f"result_{session_id}")
            os.makedirs(combined_results_dir, exist_ok=True)
            
            # Run text spanning with session-specific paths
            spanning_results = process_document(
                cell_json_path=state.cell_detection_json_path,
                ocr_json_path=state.ocr_json_path,
                output_dir=combined_results_dir,
                image_path=state.original_image_path,
                overlap_threshold=0.5,
                min_overlap_for_spanning=0.1,
                session_id=session_id
            )
            
            if not spanning_results:
                raise Exception("Text spanning failed")
            print("Text spanning complete")
            
            # Update state with spanning results paths
            state.spanning_json_path = os.path.join(combined_results_dir, "combined_with_spanning.json")
            state.spanning_viz_path = os.path.join(combined_results_dir, "visualization_with_spanning.jpg")
            
        except Exception as e:
            print(f"Error in text spanning: {e}")
            return {"error": "Text spanning failed"}
        
        # Step 5: Create final visualization
        try:
            print("Creating final visualization...")
            # Use the spanning visualization if available
            if os.path.exists(state.spanning_viz_path):
                print(f"Using text spanning visualization: {state.spanning_viz_path}")
                final_viz_path = state.spanning_viz_path
            else:
                print("Creating new visualization")
                final_viz_path = create_visualization(state)
            
            if not final_viz_path:
                raise Exception("Visualization creation failed")
            print(f"Visualization created: {final_viz_path}")
            
        except Exception as e:
            print(f"Error creating visualization: {e}")
            return {"error": "Visualization creation failed"}
        
        # Step 6: Return results
        results = {
            "success": True,
            "ocr_results": ocr_results,  # Return the processed OCR results directly
            "cell_detection": cell_detection_results,
            "text_spanning": spanning_results,
            "visualization": final_viz_path,
            "paths": {
                "original_image": state.original_image_path,
                "cell_detection_json": state.cell_detection_json_path,
                "ocr_json": state.ocr_json_path,
                "spanning_json": state.spanning_json_path,
                "spanning_viz": state.spanning_viz_path,
                "final_viz": final_viz_path
            }
        }
        
        print("Processing complete")
        return results
        
    except Exception as e:
        print(f"Error in process_image: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.route('/get_image/<path:image_path>')
def get_image(image_path):
    """
    Serve images directly from the filesystem.
    This endpoint allows viewing images referenced in the database.
    """
    try:
        # Sanitize the path to avoid directory traversal attacks
        # Only allow access to certain directories (uploads, preprocessed, output)
        allowed_prefixes = ['uploads/', 'preprocessed/', 'output/']
        
        if not any(image_path.startswith(prefix) for prefix in allowed_prefixes):
            return jsonify({'error': 'Access denied to this path'}), 403
        
        if not os.path.exists(image_path) or not os.path.isfile(image_path):
            return jsonify({'error': 'Image not found'}), 404
        
        # Determine the image type based on extension
        _, ext = os.path.splitext(image_path)
        if ext.lower() in ['.jpg', '.jpeg']:
            mimetype = 'image/jpeg'
        elif ext.lower() == '.png':
            mimetype = 'image/png'
        else:
            mimetype = 'application/octet-stream'
            
        return send_file(image_path, mimetype=mimetype)
        
    except Exception as e:
        print(f"Error serving image {image_path}: {str(e)}")
        return jsonify({'error': f'Failed to serve image: {str(e)}'}), 500

@app.route('/documents/<document_id>/image')
def get_document_image(document_id):
    """
    Get the processed image for a specific document.
    Returns the base64-encoded image for display in the UI.
    """
    try:
        conn = get_db_connection()
        doc = conn.execute('SELECT * FROM ocr_document WHERE id = ?', (document_id,)).fetchone()
        
        if not doc:
            conn.close()
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        
        # Get the image path
        image_path = doc['image_path']
        
        if not image_path or not os.path.exists(image_path):
            # Try the original image as a fallback
            image_path = doc['original_image_path']
            
        if not image_path or not os.path.exists(image_path):
            conn.close()
            return jsonify({'success': False, 'error': 'Image not found'}), 404
        
        # Load the image and convert to base64
        img = cv2.imread(image_path)
        if img is None:
            conn.close()
            return jsonify({'success': False, 'error': 'Failed to read image file'}), 500
            
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = b64encode(buffer).decode('utf-8')
        
        conn.close()
        
        return jsonify({
            'success': True,
            'image_base64': img_base64,
            'image_path': image_path
        })
        
    except Exception as e:
        print(f"Error getting document image: {str(e)}")
        return jsonify({'success': False, 'error': f'Failed to get document image: {str(e)}'}), 500

def get_original_image_base64():
    """Get the original image as base64 for display"""
    if state.original_image_path and os.path.exists(state.original_image_path):
        try:
            orig_img = cv2.imread(state.original_image_path)
            if orig_img is not None:
                _, buffer = cv2.imencode('.jpg', orig_img)
                return b64encode(buffer).decode('utf-8')
        except Exception as e:
            print(f"Error getting original image: {e}")
    return None

@app.route('/process_image', methods=['POST'])
def handle_process_image():
    """
    Handle image upload and processing request.
    """
    if 'image_file' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
        
    image_file = request.files['image_file']
    if not image_file.filename:
        return jsonify({'error': 'No selected file'}), 400
        
    try:
        # Create uploads directory if it doesn't exist
        os.makedirs('uploads', exist_ok=True)
        
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Save the uploaded file
        image_path = os.path.join('uploads', f'original_{session_id}.jpg')
        image_file.save(image_path)
        
        # Process the image
        results = process_image(image_path, session_id)
        
        if 'error' in results:
            return jsonify({'error': results['error']}), 500
            
        # Add base64 encoded images to the response
        if results['paths']['original_image']:
            results['original_image'] = get_original_image_base64()
            
        if results['paths']['final_viz']:
            img = cv2.imread(results['paths']['final_viz'])
            if img is not None:
                _, buffer = cv2.imencode('.jpg', img)
                results['image'] = b64encode(buffer).decode('utf-8')
                
        # Add flags for UI to know what processing was applied
        results['cell_detection_applied'] = bool(results.get('cell_detection'))
        results['spanning_applied'] = bool(results.get('text_spanning'))
        
        return jsonify(results)
        
    except Exception as e:
        print(f"Error processing image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize the database
    init_db()
    
    # Use port 8080 instead of the default 5000 to avoid conflicts with macOS AirPlay
    app.run(debug=True, port=8080)
