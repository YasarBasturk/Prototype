import json
import os
import numpy as np
from shapely.geometry import Polygon, Point, box
import re

def load_json_file(file_path):
    """Load JSON data from file"""
    print(f"[DEBUG] Loading JSON file from: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        loaded_json = json.load(f)
        return loaded_json

def save_json_file(data, file_path):
    """Save JSON data to file"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved combined results to {file_path}")

def text_region_to_polygon(text_region):
    """Convert text region coordinates to a Polygon"""
    # Ensure we have at least 3 points for a valid polygon
    if len(text_region) < 3:
        # If only 2 points are provided (diagonal corners), create a rectangle
        if len(text_region) == 2:
            x1, y1 = text_region[0]
            x2, y2 = text_region[1]
            return Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
        return None
    return Polygon(text_region)

def cell_to_polygon(cell):
    """Convert cell coordinates [x1, y1, x2, y2] to a Polygon"""
    x1, y1, x2, y2 = cell["coordinate"]
    return box(x1, y1, x2, y2)

def get_text_center(text_region):
    """Calculate the center point of a text region"""
    x_coords = [p[0] for p in text_region]
    y_coords = [p[1] for p in text_region]
    return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords))

def get_text_dimensions(text_region):
    """Calculate width and height of a text region"""
    x_coords = [p[0] for p in text_region]
    y_coords = [p[1] for p in text_region]
    width = max(x_coords) - min(x_coords)
    height = max(y_coords) - min(y_coords)
    return width, height

def get_overlap_percentage(text_polygon, cell_polygon):
    """Calculate what percentage of the text is inside the cell"""
    if text_polygon.intersects(cell_polygon):
        intersection_area = text_polygon.intersection(cell_polygon).area
        return intersection_area / text_polygon.area
    return 0.0

def text_fits_pattern(text, pattern_type="numeric_sequence"):
    """Check if text fits a specific pattern"""
    if pattern_type == "numeric_sequence":
        # Pattern for long numeric sequences (possibly spanning multiple cells)
        return bool(re.match(r"^\d{10,}$", text))
    elif pattern_type == "date":
        # Pattern for dates
        return bool(re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", text))
    return False

def should_split_text(text_item, cells):
    """Determine if a text item should be split across multiple cells"""
    # Check if text is unusually long
    if len(text_item.get('text', '')) > 15:
        # Check if text fits a known pattern for data that often spans cells
        if text_fits_pattern(text_item.get('text', '')):
            return True
    return False

def extract_text_items(ocr_data):
    """Extract text items from the OCR JSON structure"""
    print(f"[DEBUG] Starting extract_text_items with input type: {type(ocr_data)}")
    
    # Handle the new structure where results are wrapped in a dict
    if isinstance(ocr_data, dict) and 'results' in ocr_data:
        print("[DEBUG] Found dictionary with 'results' key, extracting results")
        ocr_data = ocr_data['results']
    
    # Handle list of results
    if isinstance(ocr_data, list):
        print(f"[DEBUG] Processing list of results, length: {len(ocr_data)}")
        text_items = []
        for idx, item in enumerate(ocr_data):
            print(f"[DEBUG] Processing item {idx}")
            if isinstance(item, dict):
                print(f"[DEBUG] Item {idx} is a dictionary")
                if item.get('type') == 'text':
                    print(f"[DEBUG] Found text item at index {idx}")
                    # Extract text and confidence from the result
                    text = item.get('res', [])
                    print(f"[DEBUG] Extracted text data: {text}")
                    
                    if isinstance(text, list) and len(text) > 0:
                        print(f"[DEBUG] Processing text list of length: {len(text)}")
                        # Handle both single text and multiple text cases
                        if isinstance(text[0], str):
                            print("[DEBUG] Processing single text string")
                            text_items.append({
                                'text': text[0],
                                'confidence': item.get('confidence', 0.0),
                                'text_region': item.get('bbox', [])
                            })
                        elif isinstance(text[0], list):
                            print(f"[DEBUG] Processing list of text items, length: {len(text)}")
                            for t_idx, t in enumerate(text):
                                if isinstance(t, list) and len(t) > 1:
                                    print(f"[DEBUG] Processing text subitem {t_idx}: {t}")
                                    text_items.append({
                                        'text': t[0],
                                        'confidence': float(t[1]) if len(t) > 1 else 0.0,
                                        'text_region': item.get('bbox', [])
                                    })
        
        print(f"[DEBUG] Finished processing. Total text items extracted: {len(text_items)}")
        return text_items
    
    # For older formats (backward compatibility)
    if isinstance(ocr_data, dict):
        if 'res' in ocr_data and isinstance(ocr_data['res'], list):
            for item in ocr_data['res']:
                if isinstance(item, dict) and 'res' in item and isinstance(item['res'], list):
                    return item['res']
            return ocr_data['res']
    
    return ocr_data.get('text_regions', [])

def split_text_for_cells(text_item, overlapping_cells):
    """Split text across multiple cells based on overlap and position"""
    text = text_item.get('text', '')
    text_region = text_item.get('text_region', [])
    confidence = text_item.get('confidence', 0.0)
    
    # If it's a numeric sequence, try to split it evenly among cells
    if text_fits_pattern(text, "numeric_sequence"):
        # Sort cells from left to right
        overlapping_cells.sort(key=lambda c: c['polygon'].bounds[0])
        
        # Calculate approximate characters per cell
        chars_per_cell = len(text) // len(overlapping_cells)
        
        split_results = []
        for i, cell in enumerate(overlapping_cells):
            start_idx = i * chars_per_cell
            end_idx = (i + 1) * chars_per_cell if i < len(overlapping_cells) - 1 else len(text)
            
            split_text = text[start_idx:end_idx]
            if split_text:
                # Create a relative text region based on the original
                # This is approximate - in a production system you'd want more precise calculation
                split_results.append({
                    'cell': cell,
                    'text': split_text,
                    'confidence': confidence,
                    'text_region': text_region  # Using original text region as an approximation
                })
                
        return split_results
    
    # For non-pattern text with multiple overlapping cells, 
    # assign to the cell with the largest overlap
    return [{
        'cell': max(overlapping_cells, key=lambda c: get_overlap_percentage(
            text_region_to_polygon(text_region), c['polygon']
        )),
        'text': text,
        'confidence': confidence,
        'text_region': text_region
    }]

def merge_cell_and_text(cell_data, ocr_data, output_path, overlap_threshold=0.5, min_overlap_for_spanning=0.1):
    """
    Merge cell detection with OCR text recognition, handling text that spans multiple cells
    
    Args:
        cell_data (dict): JSON data from cell detection
        ocr_data (dict): JSON data from OCR text recognition
        output_path (str): Path to save the combined results
        overlap_threshold (float): Threshold for text-cell overlap percentage
        min_overlap_for_spanning (float): Minimum overlap to consider a cell for spanning text
    """
    # Extract cells and text items
    cells = cell_data.get('boxes', [])
    text_items = extract_text_items(ocr_data)
    
    print(f"Found {len(cells)} cells and {len(text_items)} text items")
    
    # Convert cells to polygons for spatial operations
    cell_polygons = []
    for i, cell in enumerate(cells):
        try:
            polygon = cell_to_polygon(cell)
            cell_polygons.append({
                'id': i,
                'polygon': polygon,
                'cell_info': cell,
                'text_items': [],
                'combined_text': "",
                'confidence': 0.0
            })
        except Exception as e:
            print(f"Error processing cell {i}: {e}")
    
    # Process each text item
    unassigned_text = []
    assigned_text_ids = set()
    spanning_text_assignments = []  # Track text that spans multiple cells
    
    for i, text_item in enumerate(text_items):
        if 'text_region' not in text_item:
            continue
            
        try:
            # Convert text region to polygon
            text_polygon = text_region_to_polygon(text_item['text_region'])
            if not text_polygon:
                continue
            
            # Calculate text dimensions to identify potentially spanning text
            text_width, text_height = get_text_dimensions(text_item['text_region'])
            
            # Find all cells that have some overlap with this text
            overlapping_cells = []
            for cell_data in cell_polygons:
                overlap = get_overlap_percentage(text_polygon, cell_data['polygon'])
                if overlap >= min_overlap_for_spanning:
                    overlapping_cells.append({
                        'cell_data': cell_data, 
                        'overlap': overlap,
                        'polygon': cell_data['polygon']
                    })
            
            # Check if this text should be considered as spanning multiple cells
            if len(overlapping_cells) > 1 and should_split_text(text_item, overlapping_cells):
                # Split text across multiple cells
                split_assignments = split_text_for_cells(
                    text_item, 
                    overlapping_cells
                )
                
                for assignment in split_assignments:
                    cell = assignment['cell']['cell_data']
                    cell['text_items'].append({
                        'id': i,
                        'text': assignment['text'],
                        'confidence': assignment['confidence'],
                        'overlap': assignment['cell']['overlap'],
                        'text_region': assignment['text_region'],
                        'is_split': True,
                        'original_text': text_item.get('text', '')
                    })
                
                spanning_text_assignments.append({
                    'text_id': i,
                    'text': text_item.get('text', ''),
                    'confidence': text_item.get('confidence', 0.0),
                    'assigned_to_cells': [cell['cell_data']['id'] for cell in overlapping_cells],
                    'split_texts': [assignment['text'] for assignment in split_assignments]
                })
                
                assigned_text_ids.add(i)
                continue
                
            # Standard assignment - find best single cell
            best_cell = None
            best_overlap = 0
            
            for cell_data in cell_polygons:
                overlap = get_overlap_percentage(text_polygon, cell_data['polygon'])
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_cell = cell_data
            
            # Assign text to cell if overlap meets threshold
            if best_cell and best_overlap >= overlap_threshold:
                best_cell['text_items'].append({
                    'id': i,
                    'text': text_item.get('text', ''),
                    'confidence': text_item.get('confidence', 0.0),
                    'overlap': best_overlap,
                    'text_region': text_item['text_region']
                })
                assigned_text_ids.add(i)
            else:
                # Try a rule-based approach for unassigned text that looks like it might span cells
                if should_split_text(text_item, []):
                    # Find cells that this text might be spanning based on position
                    text_center = get_text_center(text_item['text_region'])
                    y_position = text_center[1]
                    
                    # Find cells in approximately the same row (based on y-coordinate)
                    row_cells = []
                    y_tolerance = text_height * 2  # Allow some vertical tolerance
                    
                    for cell_data in cell_polygons:
                        cell_bounds = cell_data['polygon'].bounds  # (minx, miny, maxx, maxy)
                        cell_y_center = (cell_bounds[1] + cell_bounds[3]) / 2
                        
                        if abs(cell_y_center - y_position) <= y_tolerance:
                            row_cells.append({
                                'cell_data': cell_data,
                                'polygon': cell_data['polygon'],
                                'overlap': 0  # No direct overlap
                            })
                    
                    if len(row_cells) > 0:
                        # Sort cells from left to right
                        row_cells.sort(key=lambda c: c['polygon'].bounds[0])
                        
                        # Split text across row cells
                        split_assignments = split_text_for_cells(text_item, row_cells)
                        
                        for assignment in split_assignments:
                            cell = assignment['cell']['cell_data']
                            cell['text_items'].append({
                                'id': i,
                                'text': assignment['text'],
                                'confidence': assignment['confidence'],
                                'overlap': 0,  # No direct overlap
                                'text_region': assignment['text_region'],
                                'is_split': True,
                                'original_text': text_item.get('text', ''),
                                'is_positional_assignment': True
                            })
                        
                        spanning_text_assignments.append({
                            'text_id': i,
                            'text': text_item.get('text', ''),
                            'confidence': text_item.get('confidence', 0.0),
                            'assigned_to_cells': [cell['cell_data']['id'] for cell in row_cells],
                            'split_texts': [assignment['text'] for assignment in split_assignments],
                            'assignment_method': 'positional'
                        })
                        
                        assigned_text_ids.add(i)
                        continue
                
                # Still unassigned even after trying positional assignment
                unassigned_text.append({
                    'id': i,
                    'text': text_item.get('text', ''),
                    'confidence': text_item.get('confidence', 0.0),
                    'text_region': text_item['text_region']
                })
                
        except Exception as e:
            print(f"Error processing text item {i}: {e}")
    
    # Process each cell to combine text
    for cell_data in cell_polygons:
        if cell_data['text_items']:
            # Sort text by vertical position for natural reading order
            cell_data['text_items'].sort(key=lambda x: get_text_center(x['text_region'])[1])
            
            # Combine text and calculate average confidence
            texts = [item['text'] for item in cell_data['text_items'] if item['text']]
            confidences = [item['confidence'] for item in cell_data['text_items'] if item['confidence'] > 0]
            
            cell_data['combined_text'] = " ".join(texts)
            cell_data['confidence'] = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Prepare output data
    output_data = {
        'image_path': cell_data.get('input_path', ocr_data.get('input_path', '')),
        'cells_with_text': [
            {
                'cell_id': c['id'],
                'coordinates': c['cell_info']['coordinate'],
                'text': c['combined_text'],
                'confidence': c['confidence'],
                'cell_score': c['cell_info'].get('score', 0.0),
                'component_texts': [
                    {
                        'text': item['text'],
                        'confidence': item['confidence'],
                        'text_region': item['text_region'],
                        'is_split': item.get('is_split', False),
                        'original_text': item.get('original_text', item['text']) if item.get('is_split', False) else None
                    } for item in c['text_items']
                ]
            } for c in cell_polygons if c['combined_text']
        ],
        'empty_cells': [
            {
                'cell_id': c['id'],
                'coordinates': c['cell_info']['coordinate'],
                'cell_score': c['cell_info'].get('score', 0.0)
            } for c in cell_polygons if not c['combined_text']
        ],
        'unassigned_text': [
            {
                'text_id': t['id'],
                'text': t['text'],
                'confidence': t['confidence'],
                'text_region': t['text_region']
            } for t in unassigned_text
        ],
        'spanning_text': spanning_text_assignments,
        'metadata': {
            'total_cells': len(cells),
            'total_text_items': len(text_items),
            'assigned_text_items': len(assigned_text_ids),
            'cells_with_text': len([c for c in cell_polygons if c['combined_text']]),
            'empty_cells': len([c for c in cell_polygons if not c['combined_text']]),
            'unassigned_text': len(unassigned_text),
            'spanning_text_items': len(spanning_text_assignments)
        }
    }
    
    # Save the combined results
    save_json_file(output_data, output_path)
    
    return output_data

def process_document(cell_json_path, ocr_json_path, output_dir="combined_results", 
                     image_path=None, overlap_threshold=0.5, min_overlap_for_spanning=0.1):
    """
    Process a document by combining cell detection and OCR results
    
    Args:
        cell_json_path (str): Path to JSON file with cell detection results
        ocr_json_path (str): Path to JSON file with OCR results
        output_dir (str): Directory to save outputs
        image_path (str): Path to original image (for visualization)
        overlap_threshold (float): Threshold for text-cell overlap percentage
        min_overlap_for_spanning (float): Minimum overlap to consider a cell for spanning text
        
    Returns:
        dict: Merged data structure with additional paths for visualization
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Starting text spanning process:")
    print(f"  Cell JSON: {cell_json_path}")
    print(f"  OCR JSON: {ocr_json_path}")
    print(f"  Output directory: {output_dir}")
    print(f"  Image path: {image_path}")
    
    # Get base name for output files
    base_name = os.path.basename(cell_json_path).split('.')[0]
    
    # Load input JSON files
    try:
        cell_data = load_json_file(cell_json_path)
        print(f"Loaded cell data with {len(cell_data.get('boxes', []))} cells")
    except Exception as e:
        print(f"Error loading cell data: {e}")
        return None
        
    try:
        ocr_data = load_json_file(ocr_json_path)
        text_items = extract_text_items(ocr_data)
        print(f"Loaded OCR data with {len(text_items)} text items")
    except Exception as e:
        print(f"Error loading OCR data: {e}")
        return None
    
    # Derive image path if not provided
    if not image_path:
        # Try to get it from the JSONs
        image_path = cell_data.get('input_path', ocr_data.get('input_path', ''))
        if not os.path.exists(image_path):
            print(f"Warning: Image path '{image_path}' not found.")
    
    # Merge cell and text data
    output_json_path = os.path.join(output_dir, f"{base_name}_combined_with_spanning.json")
    merged_data = merge_cell_and_text(
        cell_data, 
        ocr_data, 
        output_json_path, 
        overlap_threshold,
        min_overlap_for_spanning
    )
    
    if not merged_data:
        print("Failed to merge cell and text data")
        return None
    
    # Create visualization
    visualization_path = None
    try:
        if image_path and os.path.exists(image_path):
            vis_path = os.path.join(output_dir, f"{base_name}_visualization_with_spanning.jpg")
            visualization_path = create_visualization_with_spanning(
                cell_data, ocr_data, merged_data, vis_path, image_path
            )
            
            if visualization_path:
                print(f"Created visualization at: {visualization_path}")
                # Add the path to merged data for reference
                merged_data['visualization_path'] = visualization_path
            else:
                print(f"Failed to create visualization at: {vis_path}")
        else:
            print(f"Skipping visualization: valid image path not available")
    except Exception as e:
        print(f"Error creating visualization: {e}")
        import traceback
        traceback.print_exc()
    
    # Add paths to the output data
    merged_data['output_paths'] = {
        'json': output_json_path,
        'visualization': visualization_path
    }
    
    print(f"Processing complete for {base_name}")
    print(f"Results: {merged_data['metadata']}")
    print(f"Visualization path: {visualization_path}")
    
    return merged_data

def create_visualization_with_spanning(cell_data, ocr_data, merged_data, output_path, original_image_path):
    """Create an enhanced visualization of the merged data, highlighting spanning text"""
    import cv2
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Creating visualization with spanning at: {output_path}")
    print(f"Using original image: {original_image_path}")
    
    # Load original image
    img = cv2.imread(original_image_path)
    if img is None:
        print(f"Could not load image: {original_image_path}")
        return
        
    # Create a copy for visualization
    visualization = img.copy()
    
    # Draw cells with text
    for cell in merged_data['cells_with_text']:
        coords = cell['coordinates']
        x1, y1, x2, y2 = [int(c) for c in coords]
        
        # Check if this cell contains any split text
        has_split_text = any(item.get('is_split', False) for item in cell['component_texts'])
        
        # Draw cell rectangle - green for normal cells, purple for cells with split text
        color = (128, 0, 128) if has_split_text else (0, 255, 0)
        cv2.rectangle(visualization, (x1, y1), (x2, y2), color, 2)
        
        # Add text label
        text = cell['text']
        # Truncate if too long
        display_text = text[:20] + "..." if len(text) > 20 else text
        cv2.putText(visualization, display_text, (x1, y1-5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    # Draw empty cells in red
    for cell in merged_data['empty_cells']:
        coords = cell['coordinates']
        x1, y1, x2, y2 = [int(c) for c in coords]
        cv2.rectangle(visualization, (x1, y1), (x2, y2), (0, 0, 255), 1)
    
    # Draw unassigned text regions in blue
    for text_item in merged_data['unassigned_text']:
        region = text_item['text_region']
        points = np.array(region, dtype=np.int32)
        cv2.polylines(visualization, [points], True, (255, 0, 0), 2)
        
        # Add unassigned text label
        x, y = points[0]
        cv2.putText(visualization, text_item['text'][:10], (x, y-5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
    
    # Highlight spanning text with yellow lines connecting split parts
    if 'spanning_text' in merged_data:
        for span_item in merged_data['spanning_text']:
            # Get all cells this text spans
            cell_ids = span_item['assigned_to_cells']
            
            # Find cell centers
            centers = []
            for cell_id in cell_ids:
                # Find the cell with this ID
                for cell in merged_data['cells_with_text']:
                    if cell['cell_id'] == cell_id:
                        coords = cell['coordinates']
                        center_x = (coords[0] + coords[2]) // 2
                        center_y = (coords[1] + coords[3]) // 2
                        centers.append((int(center_x), int(center_y)))
                        break
            
            # Draw lines connecting cells with this spanning text
            if len(centers) > 1:
                for i in range(len(centers) - 1):
                    cv2.line(visualization, centers[i], centers[i+1], (0, 255, 255), 2)
                
                # Add spanning text label at the midpoint
                mid_idx = len(centers) // 2
                mid_x, mid_y = centers[mid_idx]
                
                # Place the label above the midpoint
                label_y = mid_y - 25
                
                # Add the original text as a label
                original_text = span_item['text']
                display_text = original_text[:15] + "..." if len(original_text) > 15 else original_text
                cv2.putText(visualization, display_text, (mid_x - 50, label_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 2)
    
    # Save visualization
    try:
        print(f"Saving visualization to: {output_path}")
        cv2.imwrite(output_path, visualization)
        if os.path.exists(output_path):
            print(f"✓ Visualization saved successfully at: {output_path}")
            print(f"  File size: {os.path.getsize(output_path)} bytes")
        else:
            print(f"✗ Failed to save visualization - file does not exist after save attempt")
    except Exception as e:
        print(f"Error saving visualization: {e}")
    
    # Return path if successful
    return output_path if os.path.exists(output_path) else None

# Example usage
if __name__ == "__main__":
    cell_json_path = "test/paddleX 2/IMG_5073_res.json"  # From cell detection
    ocr_json_path = "output/paddle-ocr-detection/processed/res_0.json"  # From PP-StructureV2
    image_path = "./inputs/IMG_5073.png"  # Original image
    
    merged_data = process_document(
        cell_json_path=cell_json_path,
        ocr_json_path=ocr_json_path,
        output_dir="combined_results",
        image_path=image_path,
        overlap_threshold=0.5,  # Lower threshold to catch more text
        min_overlap_for_spanning=0.1  # Low threshold to identify spanning text
    )