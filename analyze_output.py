import json
import os
# import argparse # Kommenteret ud, da vi hardkoder stier

# Levenshtein og relaterede funktioner fjernes efter brugerønske

def load_json_file(file_path):
    """Indlæser en JSON-fil og returnerer dens indhold."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Fejl: Filen blev ikke fundet: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Fejl: Kunne ikke dekode JSON fra filen: {file_path}")
        return None
    except Exception as e:
        print(f"Der opstod en uventet fejl under indlæsning af {file_path}: {e}")
        return None

# extract_all_text, calculate_cer, calculate_wer fjernet

def analyze_detailed_confidence(data, data_source_name="Data"):
    """
    Beregner og udskriver gennemsnitlige konfidensscorer for tekstgenkendelse og celledetektion.
    """
    print(f"\n--- Detaljeret Konfidensanalyse for: {data_source_name} ---")

    text_confidences = []
    cell_scores = []

    if not isinstance(data, dict):
        print(f"Advarsel: {data_source_name} data er ikke en dictionary. Kan ikke analysere konfidens.")
        return

    # Uddrag tekstkonfidenser og cellescores fra 'cells_with_text'
    for cell in data.get("cells_with_text", []):
        if isinstance(cell, dict):
            if isinstance(cell.get("cell_score"), (int, float)):
                cell_scores.append(cell["cell_score"])
            
            for component in cell.get("component_texts", []):
                if isinstance(component, dict) and isinstance(component.get("confidence"), (int, float)):
                    text_confidences.append(component["confidence"])

    # Uddrag cellescores fra 'empty_cells'
    for cell in data.get("empty_cells", []):
        if isinstance(cell, dict) and isinstance(cell.get("cell_score"), (int, float)):
            cell_scores.append(cell["cell_score"])
    
    # Beregn og udskriv resultater for Tekstgenkendelse
    if text_confidences:
        avg_text_confidence = sum(text_confidences) / len(text_confidences)
        print(f"Gennemsnitlig Tekstgenkendelses-konfidens: {avg_text_confidence:.4f} (fra {len(text_confidences)} tekst-elementer)")
    else:
        print("Ingen tekst-elementer med konfidensscore fundet.")

    # Beregn og udskriv resultater for Celledetektion
    if cell_scores:
        avg_cell_score = sum(cell_scores) / len(cell_scores)
        print(f"Gennemsnitlig Celledetektions-score: {avg_cell_score:.4f} (fra {len(cell_scores)} celler)")
    else:
        print("Ingen celler med score fundet.")

def analyze_pipeline_output(output_json_path, ground_truth_json_path):
    """
    Analyserer output fra web-pipelinen mod et ground truth.
    """
    print(f"\n--- Analyserer Output: {os.path.basename(output_json_path)} ---")
    print(f"--- Mod Ground Truth: {os.path.basename(ground_truth_json_path)} ---")

    output_data = load_json_file(output_json_path)
    gt_data = load_json_file(ground_truth_json_path)

    if output_data is None or gt_data is None:
        print("Analyse afbrudt på grund af fejl ved indlæsning af filer.")
        return None

    results = {} 

    # 1. Antal Celler (Output) og Output Metadata
    num_output_cells = 0
    if isinstance(output_data, dict):
        cells_with_text = output_data.get("cells_with_text", [])
        empty_cells = output_data.get("empty_cells", [])
        
        if isinstance(cells_with_text, list):
            num_output_cells += len(cells_with_text)
            
        if isinstance(empty_cells, list):
            num_output_cells += len(empty_cells)
        
        print(f"Antal celler (Output): {num_output_cells}")

        print("\n--- Output Pipeline Metadata ---")
        output_metadata = output_data.get("metadata", {})
        if isinstance(output_metadata, dict):
            if output_metadata:
                for key, value in output_metadata.items():
                    print(f"  {key}: {value}")
            else:
                print("  Metadata-objektet er tomt i Output Pipeline.")
        else:
            print(f"  Advarsel: 'metadata' er ikke et objekt (dictionary) i {output_json_path}")
    else:
        print(f"Advarsel: Output data fra {output_json_path} er ikke en dictionary.")
        print(f"Antal celler (Output): N/A (Output ikke dict)")

    # 2. Ground Truth Metadata og Antal Celler (Ground Truth)
    print("\n--- Ground Truth Metadata ---")
    num_gt_cells_from_metadata = "N/A"
    if isinstance(gt_data, dict):
        gt_metadata = gt_data.get("metadata", {})
        if isinstance(gt_metadata, dict):
            if gt_metadata:
                for key, value in gt_metadata.items():
                    print(f"  {key}: {value}")
                num_gt_cells_from_metadata = gt_metadata.get('total_cells', "N/A (total_cells mangler i metadata)")
            else:
                print("  Metadata-objektet er tomt i Ground Truth.")
                num_gt_cells_from_metadata = "N/A (metadata tomt)"
        else:
            print(f"  Advarsel: 'metadata' er ikke et objekt (dictionary) i {ground_truth_json_path}")
            num_gt_cells_from_metadata = "N/A (metadata ikke et objekt)"
    else:
        print(f"  Advarsel: Ground truth data fra {ground_truth_json_path} er ikke en dictionary.")
        num_gt_cells_from_metadata = "N/A (GT data ikke et objekt)"

    # 3. Detaljeret Konfidensanalyse
    analyze_detailed_confidence(output_data, "Output Pipeline")
    analyze_detailed_confidence(gt_data, "Ground Truth")
    
    # Den returnerede værdi fra calculate_mean_confidence gemmes ikke i `results` 
    # da vi ikke har en opsummering mere, men kunne gøres hvis det ønskes.
    
    return results

def main():
    # Hardkodede stier - rediger disse efter behov
    pipeline_output_json_file = "output/merge and split/IMG_5073_ingen_preprocess.json" 
    ground_truth_json_file = "output/merge and split/processed_IMG_5073_res_combined_with_spanning.json"

    print(f"Bruger output JSON: {pipeline_output_json_file}")
    print(f"Bruger ground truth JSON: {ground_truth_json_file}")

    if not os.path.exists(pipeline_output_json_file):
        print(f"FEJL: Output-JSON filen blev ikke fundet: {pipeline_output_json_file}")
        return

    if not os.path.exists(ground_truth_json_file):
        print(f"FEJL: Ground truth JSON filen blev ikke fundet: {ground_truth_json_file}")
        return

    analyze_pipeline_output(pipeline_output_json_file, ground_truth_json_file)

if __name__ == "__main__":
    main() 