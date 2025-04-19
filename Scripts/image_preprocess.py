import cv2
import numpy as np
import argparse
import os


#Deskew – Corrects small rotations in the image
def deskew_image(image):
    """Deskew the image if it has a minor rotation."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Threshold to find text regions
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # Get coordinates of all non-zero pixels
    coords = np.column_stack(np.where(thresh > 0))
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    
    # Correct angle so it's between -45 and +45
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), 
                             flags=cv2.INTER_CUBIC, 
                             borderMode=cv2.BORDER_REPLICATE)
    return rotated

#CLAHE – Corrects uneven lighting
def clahe_enhance(image):
    """Apply CLAHE for local contrast enhancement."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    merged = cv2.merge((cl, a, b))
    enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    return enhanced
#Gamma – Corrects overall brightness
def gamma_correction(image, gamma=1.2):
    """Adjust overall brightness via gamma correction."""
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 
                      for i in range(256)]).astype("uint8")
    return cv2.LUT(image, table)

def find_document_corners(image, min_area_ratio=0.3):
    """Try to locate a rectangular contour that occupies at least `min_area_ratio` of the image."""
    h, w = image.shape[:2]
    img_area = h * w
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 200)

    # Morphological close to connect broken edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area_ratio * img_area:
            # skip if too small to be the full document
            continue
        
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        
        if len(approx) == 4:
            return approx.reshape((4, 2))
    return None
#Order points – Orders the corner points of the document
def order_points(pts):
    """Order corner points [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    rect[1] = pts[np.argmin(diff)]# top-right
    rect[3] = pts[np.argmax(diff)]# bottom-left
    
    return rect

def dewarp_image(image, min_area_ratio=0.3):
    """Perform perspective transform if a 4-corner document is detected."""
    corners = find_document_corners(image, min_area_ratio=min_area_ratio)
    if corners is None:
        # No suitable rectangle found, return as-is
        return image
    
    rect = order_points(corners)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped


def debug_preprocessing(img_path, output_prefix="debug_step"):
    """Debug function that outputs each preprocessing step as a separate image."""
    import os
    
    # Create output directory if it doesn't exist
    output_dir = "output/image-preprocessing"
    os.makedirs(output_dir, exist_ok=True)

    # Load original
    image = cv2.imread(img_path)
    step_count = 1

    # Step 0: Save the original to compare later
    cv2.imwrite(f"{output_dir}/{output_prefix}_{step_count}_original.jpg", image)
    step_count += 1

    # Step 1: Deskew
    #deskewed = deskew_image(image)
    #cv2.imwrite(f"{output_dir}/{output_prefix}_{step_count}_deskewed.jpg", deskewed)
    #step_count += 1

    # Step 2: Dewarp
    dewarped = dewarp_image(image, min_area_ratio=0.3)
    cv2.imwrite(f"{output_dir}/{output_prefix}_{step_count}_dewarped.jpg", dewarped)
    step_count += 1

    # Step 3: CLAHE
    clahe_result = clahe_enhance(dewarped)
    cv2.imwrite(f"{output_dir}/{output_prefix}_{step_count}_clahe.jpg", clahe_result)
    step_count += 1

    # Step 4: Gamma correction
    gamma_result = gamma_correction(clahe_result, gamma=1.2)
    cv2.imwrite(f"{output_dir}/{output_prefix}_{step_count}_gamma.jpg", gamma_result)
    step_count += 1

    return gamma_result

# Add new function for command-line usage without modifying existing code
def preprocess_image(input_path, output_path):
    """Process an image through the full preprocessing pipeline and save the result."""
    # Make sure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Load image
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Could not read image from {input_path}")
    
    # Apply preprocessing steps (similar to debug_preprocessing)
    # Step 1: Dewarp
    dewarped = dewarp_image(image, min_area_ratio=0.3)
    
    # Step 2: CLAHE
    clahe_result = clahe_enhance(dewarped)
    
    # Step 3: Gamma correction
    final_result = gamma_correction(clahe_result, gamma=1.2)
    
    # Save the result
    cv2.imwrite(output_path, final_result)
    print(f"Processed image saved to {output_path}")
    
    return final_result

# Only add this part to enable command-line arguments without affecting existing code
if __name__ == "__main__":
    # If arguments are provided, use them
    if len(os.sys.argv) > 1:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Preprocess an image for OCR.')
        parser.add_argument('--input', type=str, help='Path to input image')
        parser.add_argument('--output', type=str, help='Path to save processed image')
        
        args = parser.parse_args()
        
        # If both input and output are provided, run preprocessing
        if args.input and args.output:
            preprocess_image(args.input, args.output)
        else:
            print("Both --input and --output arguments are required.")
    else:
        # Original code - run debug preprocessing
        final_image = debug_preprocessing("input/IMG_5063.png", output_prefix="my_debug")