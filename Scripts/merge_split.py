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
    if len(text_region) < 3:
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

def text_fits_pattern(text, pattern_type="long_text_general"):
    """Check if text fits a specific pattern. For now, numeric_sequence is kept for potential specific use cases, but general splitting is prioritized."""
    if pattern_type == "numeric_sequence":
        # Bevaret hvis specifik numerisk logik ønskes et andet sted, men ikke primær for splitting
        return bool(re.match(r"^\d{10,}$", text))
    elif pattern_type == "date":
        return bool(re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", text))
    # For generel splitting baseret på længde, er denne funktion mindre relevant nu.
    return False # Default til False hvis mønster ikke genkendes

def should_split_text(text_item, cells_overlapped_count):
    """Determine if a text item should be considered for splitting based on length and if it overlaps multiple cells."""
    text_length_threshold = 10 # Kan justeres (ændret fra 15)
    text = text_item.get('text', '')

    if len(text) > text_length_threshold and cells_overlapped_count > 1:
        # Teksten er lang nok OG den overlapper med mere end én celle
        # Vi behøver ikke et specifikt mønster (som kun tal) for at overveje splitting
        return True
    
    # Ny tilføjelse: Overvej også splitting for den positionelle tildeling, hvis teksten er lang
    # Dette er for tilfældet hvor `cells_overlapped_count` er 0 (fra `unassigned_text` logikken)
    if len(text) > text_length_threshold and cells_overlapped_count == 0:
         # Dette er til den del af koden, der kalder should_split_text med `overlapping_cells=[]` (reelt `cells_overlapped_count=0`)
         # for at se om en u-tildelt tekst BLOT PGA SIN LÆNGDE skal forsøges positionelt splittet.
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
    """
    Split text across multiple cells based on overlap and position.
    Splitting er nu mere generel og ikke kun for numeriske sekvenser.
    """
    text = text_item.get('text', '')
    text_region = text_item.get('text_region', [])
    confidence = text_item.get('confidence', 0.0)
    
    if not overlapping_cells: # Safety check
        return []

    # Hvis der er mere end én overlappende celle, forsøges splitting.
    # Den tidligere betingelse om text_fits_pattern(text, "numeric_sequence") er fjernet herfra
    # for at gøre splitting mere generel.
    if len(overlapping_cells) > 1:
        # Sort cells from left to right (eller top-til-bund, afhængig af forventet tekstflow for spændende celler)
        # For nu, lad os beholde sortering fra venstre mod højre. Kan justeres hvis nødvendigt.
        overlapping_cells.sort(key=lambda c: c['polygon'].bounds[0])
        
        # Calculate approximate characters per cell
        # Denne simple fordeling kan være naiv for komplekse layouts, men er et udgangspunkt.
        num_cells_to_split_over = len(overlapping_cells)
        chars_per_cell = len(text) // num_cells_to_split_over if num_cells_to_split_over > 0 else len(text)
        
        split_results = []
        current_pos = 0
        for i, cell_info_dict in enumerate(overlapping_cells):
            # Den 'cell' vi vil tildele til, er inde i 'cell_info_dict'
            cell_to_assign = cell_info_dict['cell_data'] # Antager 'cell_data' nøglen fra `merge_cell_and_text`
            
            # Hvis det er den sidste celle, tag resten af teksten
            if i == num_cells_to_split_over - 1:
                split_text_segment = text[current_pos:]
            else:
                split_text_segment = text[current_pos : current_pos + chars_per_cell]
            
            if split_text_segment: # Kun tilføj hvis der er tekst
                split_results.append({
                    'cell': cell_to_assign, # Skal være selve celle-objektet der kan modtage tekst
                    'text': split_text_segment,
                    'confidence': confidence, # Bevar original konfidens for alle segmenter
                    'text_region': text_region,  # Bevar original text_region, da det er svært at splitte præcist
                    'overlap': cell_info_dict.get('overlap', 0) # Bevar overlap info hvis det findes
                })
            current_pos += len(split_text_segment)
            if current_pos >= len(text):
                break # Al tekst er fordelt
                
        return split_results
    
    # Hvis kun én overlappende celle (eller logikken førte hertil med én celle), tildel hele teksten.
    # (Denne del bevares for enkelt-celle overlap eller som fallback)
    return [{
        'cell': overlapping_cells[0]['cell_data'], # Antager 'cell_data' nøglen
        'text': text,
        'confidence': confidence,
        'text_region': text_region,
        'overlap': overlapping_cells[0].get('overlap', 0)
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
    cells = cell_data.get('boxes', [])
    text_items = extract_text_items(ocr_data)
    
    print(f"Found {len(cells)} cells and {len(text_items)} text items")
    
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
    
    unassigned_text = []
    assigned_text_ids = set()
    spanning_text_assignments = []
    
    for i, text_item in enumerate(text_items):
        if 'text_region' not in text_item or not text_item.get('text', '').strip(): # Spring over hvis ingen text_region eller tom tekst
            continue
            
        try:
            text_polygon = text_region_to_polygon(text_item['text_region'])
            if not text_polygon:
                continue
            
            text_width, text_height = get_text_dimensions(text_item['text_region'])
            
            overlapping_cells_with_details = [] # Skal indeholde dicts med 'cell_data', 'overlap', 'polygon'
            for cell_poly_data in cell_polygons:
                overlap = get_overlap_percentage(text_polygon, cell_poly_data['polygon'])
                if overlap >= min_overlap_for_spanning: # Brug min_overlap_for_spanning her for at samle kandidater
                    overlapping_cells_with_details.append({
                        'cell_data': cell_poly_data, 
                        'overlap': overlap,
                        'polygon': cell_poly_data['polygon'] # Bruges til sortering i split_text_for_cells
                    })
            
            # Brug den modificerede should_split_text
            # Argumentet er nu antallet af celler, teksten overlapper med (over min_overlap_for_spanning)
            if should_split_text(text_item, len(overlapping_cells_with_details)):
                split_assignments = split_text_for_cells(
                    text_item, 
                    overlapping_cells_with_details # Send listen af dicts
                )
                
                if split_assignments: # Kun hvis der faktisk blev lavet assignments
                    assigned_this_item = False
                    original_text_for_span_item = text_item.get('text', '')
                    cells_assigned_to_ids = []
                    split_texts_for_span_item = []

                    for assignment in split_assignments:
                        # 'cell' fra split_assignments er 'cell_data' objektet
                        target_cell_data = assignment['cell'] 
                        target_cell_data['text_items'].append({
                            'id': i, # ID for det oprindelige text_item
                            'text': assignment['text'],
                            'confidence': assignment['confidence'],
                            'overlap': assignment['overlap'],
                            'text_region': assignment['text_region'],
                            'is_split': True,
                            'original_text': original_text_for_span_item
                        })
                        assigned_this_item = True
                        cells_assigned_to_ids.append(target_cell_data['id'])
                        split_texts_for_span_item.append(assignment['text'])
                    
                    if assigned_this_item:
                        spanning_text_assignments.append({
                            'text_id': i,
                            'text': original_text_for_span_item,
                            'confidence': text_item.get('confidence', 0.0),
                            'assigned_to_cells': list(set(cells_assigned_to_ids)), # unikke celle IDs
                            'split_texts': split_texts_for_span_item
                        })
                        assigned_text_ids.add(i)
                        continue # Gå til næste text_item
                # Hvis split_assignments var tom, eller hvis logikken skal fortsætte til enkelt tildeling
                # (Dette 'else' er måske ikke nødvendigt hvis 'continue' altid rammes ved succesfuld split)

            # Standard enkelt-celle tildeling (hvis ikke splittet, eller hvis splitting mislykkedes)
            # Genberegn bedste overlap baseret på den strengere `overlap_threshold` for enkelt tildeling
            best_single_cell = None
            highest_overlap_for_single_assignment = 0.0
            
            for cell_data_for_single in cell_polygons: # Iterer over de oprindelige cell_polygons
                overlap_for_single = get_overlap_percentage(text_polygon, cell_data_for_single['polygon'])
                if overlap_for_single > highest_overlap_for_single_assignment:
                    highest_overlap_for_single_assignment = overlap_for_single
                    best_single_cell = cell_data_for_single
            
            if best_single_cell and highest_overlap_for_single_assignment >= overlap_threshold:
                best_single_cell['text_items'].append({
                    'id': i,
                    'text': text_item.get('text', ''),
                    'confidence': text_item.get('confidence', 0.0),
                    'overlap': highest_overlap_for_single_assignment,
                    'text_region': text_item['text_region'],
                    'is_split': False # Ikke splittet i dette tilfælde
                })
                assigned_text_ids.add(i)
            else:
                # Forsøg på positionel tildeling for u-tildelt tekst (hvis den er lang nok)
                # Her bruges should_split_text med cells_overlapped_count = 0 for at tjekke tekstlængde
                if should_split_text(text_item, 0): 
                    text_center = get_text_center(text_item['text_region'])
                    y_position = text_center[1]
                    y_tolerance = text_height * 2 
                    
                    row_cells_for_positional = [] # Skal være en liste af dicts som overlapping_cells_with_details
                    for cell_poly_data_pos in cell_polygons:
                        cell_bounds = cell_poly_data_pos['polygon'].bounds
                        cell_y_center = (cell_bounds[1] + cell_bounds[3]) / 2
                        if abs(cell_y_center - y_position) <= y_tolerance:
                            row_cells_for_positional.append({
                                'cell_data': cell_poly_data_pos,
                                'polygon': cell_poly_data_pos['polygon'],
                                'overlap': 0 # Ingen direkte overlap
                            })
                    
                    if row_cells_for_positional: # Kun hvis der er celler på samme række
                        # Sorter fra venstre mod højre
                        row_cells_for_positional.sort(key=lambda c: c['polygon'].bounds[0])
                        
                        positional_split_assignments = split_text_for_cells(text_item, row_cells_for_positional)
                        
                        if positional_split_assignments:
                            assigned_this_item_positionally = False
                            original_text_for_pos_span = text_item.get('text', '')
                            pos_cells_assigned_to_ids = []
                            pos_split_texts = []

                            for assignment in positional_split_assignments:
                                target_cell_data_pos = assignment['cell']
                                target_cell_data_pos['text_items'].append({
                                    'id': i,
                                    'text': assignment['text'],
                                    'confidence': assignment['confidence'],
                                    'overlap': 0, 
                                    'text_region': assignment['text_region'],
                                    'is_split': True,
                                    'original_text': original_text_for_pos_span,
                                    'is_positional_assignment': True
                                })
                                assigned_this_item_positionally = True
                                pos_cells_assigned_to_ids.append(target_cell_data_pos['id'])
                                pos_split_texts.append(assignment['text'])

                            if assigned_this_item_positionally:
                                spanning_text_assignments.append({
                                    'text_id': i,
                                    'text': original_text_for_pos_span,
                                    'confidence': text_item.get('confidence', 0.0),
                                    'assigned_to_cells': list(set(pos_cells_assigned_to_ids)),
                                    'split_texts': pos_split_texts,
                                    'assignment_method': 'positional'
                                })
                                assigned_text_ids.add(i)
                                continue # Gå til næste text_item
                
                # Hvis stadig ikke tildelt, så er den unassigned
                if i not in assigned_text_ids:
                    unassigned_text.append({
                        'id': i, # Korrekt ID for det oprindelige text_item
                        'text': text_item.get('text', ''),
                        'confidence': text_item.get('confidence', 0.0),
                        'text_region': text_item['text_region']
                    })
                
        except Exception as e:
            print(f"Error processing text item {i} ('{text_item.get('text', '')[:30]}...'): {e}")
            import traceback
            traceback.print_exc() # Print fuld traceback for fejlfinding
    
    # Process each cell to combine text
    for cell_data in cell_polygons:
        if cell_data['text_items']:
            cell_data['text_items'].sort(key=lambda x: get_text_center(x['text_region'])[1])
            texts = [item['text'] for item in cell_data['text_items'] if item.get('text')] # Tjek om 'text' eksisterer
            confidences = [item['confidence'] for item in cell_data['text_items'] if isinstance(item.get('confidence'), (int,float)) and item['confidence'] > 0]
            cell_data['combined_text'] = " ".join(texts).strip()
            cell_data['confidence'] = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Prepare output data
    output_data = {
        'image_path': cell_data.get('input_path', ocr_data.get('input_path', '')), # Fejl her, cell_data er sidste i loop
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
                        'original_text': item.get('original_text', item['text']) if item.get('is_split', False) else None,
                        'is_positional_assignment': item.get('is_positional_assignment', False)
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
        'unassigned_text': [ # Sikrer at unassigned_text har de korrekte nøgler
            {
                'text_id': t['id'], # Var 'id', skal være 'text_id' for konsistens med metadata
                'text': t['text'],
                'confidence': t['confidence'],
                'text_region': t['text_region']
            } for t in unassigned_text
        ],
        'spanning_text': spanning_text_assignments,
        'metadata': {
            'total_cells': len(cells),
            'total_text_items': len(text_items), # Antal oprindelige tekst items
            'assigned_text_items': len(assigned_text_ids), # Antal *oprindelige* tekst items der blev tildelt (enten som helhed eller splittet)
            'cells_with_text': len([c for c in cell_polygons if c['combined_text']]),
            'empty_cells': len([c for c in cell_polygons if not c['combined_text']]),
            'unassigned_text': len(unassigned_text), # Antal *oprindelige* tekst items der forblev u-tildelt
            'spanning_text_items': len(spanning_text_assignments) # Antal *oprindelige* tekst items der blev identificeret som spændende
        }
    }
    # Rettelse for image_path i output_data
    if cell_data: # Check om cell_data er tilgængelig (dvs. der var celler)
         output_data['image_path'] = cell_data.get('input_path', ocr_data.get('input_path', ''))
    elif ocr_data:
         output_data['image_path'] = ocr_data.get('input_path', '')
    else:
         output_data['image_path'] = ''


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
        cell_data_loaded = load_json_file(cell_json_path) # Ændret variabelnavn for at undgå scope konflikt
        print(f"Loaded cell data with {len(cell_data_loaded.get('boxes', []))} cells")
    except Exception as e:
        print(f"Error loading cell data: {e}")
        return None
        
    try:
        ocr_data_loaded = load_json_file(ocr_json_path) # Ændret variabelnavn
        # Bevar den oprindelige ocr_data_loaded til metadata, hvis extract_text_items modificerer den
        text_items_count_check = extract_text_items(ocr_data_loaded) 
        print(f"Loaded OCR data with {len(text_items_count_check)} text items")
    except Exception as e:
        print(f"Error loading OCR data: {e}")
        return None
    
    # Derive image path if not provided
    current_image_path = image_path # Brug et nyt variabelnavn
    if not current_image_path:
        # Try to get it from the JSONs
        current_image_path = cell_data_loaded.get('input_path', ocr_data_loaded.get('input_path', ''))
        if not os.path.exists(current_image_path):
            print(f"Warning: Image path '{current_image_path}' not found.")
    
    # Merge cell and text data
    output_json_path = os.path.join(output_dir, f"{base_name}_combined_with_spanning.json")
    merged_data = merge_cell_and_text(
        cell_data_loaded, 
        ocr_data_loaded, 
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
        if current_image_path and os.path.exists(current_image_path):
            vis_path = os.path.join(output_dir, f"{base_name}_visualization_with_spanning.jpg")
            visualization_path = create_visualization_with_spanning(
                cell_data_loaded, ocr_data_loaded, merged_data, vis_path, current_image_path
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

def create_visualization_with_spanning(cell_data_vis, ocr_data_vis, merged_data, output_path, original_image_path_vis): # Ændret param navne
    """Create an enhanced visualization of the merged data, highlighting spanning text"""
    import cv2
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Creating visualization with spanning at: {output_path}")
    print(f"Using original image: {original_image_path_vis}")
    
    # Load original image
    img = cv2.imread(original_image_path_vis)
    if img is None:
        print(f"Could not load image: {original_image_path_vis}")
        return None # Returner None hvis billedet ikke kan loades
        
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
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1) # Farve for tekstlabel ændret til rød for synlighed
    
    # Draw empty cells in red
    for cell in merged_data['empty_cells']:
        coords = cell['coordinates']
        x1, y1, x2, y2 = [int(c) for c in coords]
        cv2.rectangle(visualization, (x1, y1), (x2, y2), (0, 0, 255), 1)
    
    # Draw unassigned text regions in blue
    if 'unassigned_text' in merged_data: # Tjek om nøglen findes
        for text_item in merged_data['unassigned_text']:
            if 'text_region' in text_item and text_item['text_region']: # Tjek om text_region eksisterer og ikke er tom
                region = text_item['text_region']
                points = np.array(region, dtype=np.int32)
                cv2.polylines(visualization, [points], True, (255, 0, 0), 2)
                
                # Add unassigned text label
                x, y = points[0]
                cv2.putText(visualization, text_item.get('text', '')[:10], (x, y-5), 
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
                for cell_obj in merged_data['cells_with_text']: # Brug 'cell_obj' for at undgå navnekonflikt
                    if cell_obj['cell_id'] == cell_id:
                        coords = cell_obj['coordinates']
                        center_x = (coords[0] + coords[2]) // 2
                        center_y = (coords[1] + coords[3]) // 2
                        centers.append((int(center_x), int(center_y)))
                        break
            
            # Draw lines connecting cells with this spanning text
            if len(centers) > 1:
                for i_line in range(len(centers) - 1): # Brug 'i_line' for at undgå navnekonflikt
                    cv2.line(visualization, centers[i_line], centers[i_line+1], (0, 255, 255), 2) # Gul
                
                # Add spanning text label at the midpoint
                mid_idx = len(centers) // 2
                mid_x, mid_y = centers[mid_idx]
                
                # Place the label above the midpoint
                label_y = mid_y - 25
                
                # Add the original text as a label
                original_text = span_item['text']
                display_text = original_text[:15] + "..." if len(original_text) > 15 else original_text
                cv2.putText(visualization, display_text, (mid_x - 50, label_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 2) # Mørkere gul/orange
    
    # Save visualization
    try:
        print(f"Saving visualization to: {output_path}")
        save_success = cv2.imwrite(output_path, visualization) # Gem returværdi
        if save_success and os.path.exists(output_path):
            print(f"✓ Visualization saved successfully at: {output_path}")
            print(f"  File size: {os.path.getsize(output_path)} bytes")
        else:
            print(f"✗ Failed to save visualization (imwrite returned {save_success} or file does not exist)")
    except Exception as e:
        print(f"Error saving visualization: {e}")
        import traceback
        traceback.print_exc()
        return None # Returner None ved fejl
    
    # Return path if successful
    return output_path if os.path.exists(output_path) else None


if __name__ == "__main__":
    # Sørg for at stierne er korrekte for din test
    # Eksempel stier - du skal muligvis justere disse
    # cell_json_path = "output/cell detection/processed_IMG_5073_res.json"
    # ocr_json_path = "output/ai-model/processed_IMG_5073/res_0.json" 
    # image_path = "input_images/IMG_5073.png" # Antager en input_images mappe

    # For at teste med specifikke filer fra tidligere diskussion:
    cell_json_path = "output/cell detection/processed_Image_brightness_1_res.json"
    ocr_json_path = "output/ai-model/processed_Image_brightness_1/res_0.json"
    image_path = "output/preprocessed/processed_Image_brightness_1.1.png" # Det forbehandlede billede
    
    # Tjek om input-filerne eksisterer før kørsel
    if not os.path.exists(cell_json_path):
        print(f"FEJL: Cell JSON-fil ikke fundet: {cell_json_path}")
    elif not os.path.exists(ocr_json_path):
        print(f"FEJL: OCR JSON-fil ikke fundet: {ocr_json_path}")
    elif not os.path.exists(image_path):
        print(f"FEJL: Billedfil ikke fundet: {image_path}")
    else:
        merged_data_result = process_document( # Ændret variabelnavn
            cell_json_path=cell_json_path,
            ocr_json_path=ocr_json_path,
            output_dir="output/merge_and_split_results", # Opdateret output dir for test
            image_path=image_path,
            overlap_threshold=0.4,  # Justeret threshold for test
            min_overlap_for_spanning=0.05 # Justeret threshold for test
        )
        if merged_data_result:
            print("\nSuccessfully processed document:")
            # print(json.dumps(merged_data_result, indent=2, ensure_ascii=False)) # Udskriv hele resultatet
        else:
            print("\nFailed to process document.")