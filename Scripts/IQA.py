import cv2
import numpy as np
from PIL import Image
import os
import torch
import logging
import easyocr

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageQualityAssessor:
    def __init__(self, min_resolution=(640, 480),
                 blur_threshold=40,
                 brightness_range=(0.2, 1.1),
                 ocr_languages=['en'], # Language(s) for EasyOCR
                 ocr_min_confidence=0.6): # Minimum average confidence to pass

        logger.info("Initializing ImageQualityAssessor...")
        self.min_resolution = min_resolution
        self.blur_threshold = blur_threshold
        self.brightness_range = brightness_range
        self.ocr_min_confidence = ocr_min_confidence

        # Initialize EasyOCR Reader
        # Use GPU if available, otherwise CPU
        use_gpu = torch.cuda.is_available()
        logger.info(f"Initializing EasyOCR Reader for languages: {ocr_languages} (GPU: {use_gpu})...")
        try:
            # Note: First time running might download language models
            self.reader = easyocr.Reader(ocr_languages, gpu=use_gpu)
            logger.info("EasyOCR Reader initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing EasyOCR Reader: {str(e)}")
            # Fallback or re-raise depending on desired behavior
            raise RuntimeError(f"Failed to initialize EasyOCR: {e}") from e

    def _run_ocr(self, image_data):
        """Run EasyOCR and return analysis."""
        try:
            if image_data is None:
                 logger.error("OCR Step: Received None as image data.")
                 return {"error": "Received None as image data", "average_confidence": 0.0}

            logger.info(f"OCR Step: Processing image data with shape: {image_data.shape}")
            ocr_results = self.reader.readtext(image_data, detail=1)

            total_confidence = 0
            detected_texts = []

            if ocr_results:
                for (bbox, text, conf) in ocr_results:
                    total_confidence += conf
                    detected_texts.append(text)
                average_confidence = total_confidence / len(ocr_results)
            else:
                average_confidence = 0.0 # No text found

            logger.info(f"OCR Step: Processed image with avg confidence {average_confidence:.2f}")
            return {
                "average_confidence": average_confidence,
                "texts": detected_texts
            }

        except Exception as e:
            logger.exception(f"Error during OCR processing with direct data: {str(e)}")
            return {"error": str(e), "average_confidence": 0.0}

    def assess_image(self, image_data):
        """Assess an image using traditional checks and OCR quality based on image data."""
        logger.info("Assessing image data...")
        try:
            # We already have image_data (NumPy array), no need to read from path
            if image_data is None:
                logger.error("assess_image received None as image data.")
                return {"status": "error", "message": "Received invalid image data"}

            # Use image_data (cv_img) directly for OpenCV checks
            cv_img = image_data
            logger.info(f"Image data received. Shape: {cv_img.shape}")

            # Convert to PIL image for checks requiring it
            try:
                # OpenCV uses BGR, PIL uses RGB
                pil_img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
                logger.info(f"Converted to PIL Image. Size: {pil_img.size}")
            except Exception as pil_e:
                logger.error(f"Could not convert image data to PIL: {pil_e}")
                return {"status": "error", "message": f"Could not convert image data to PIL: {pil_e}"}

            # Run traditional quality checks
            logger.info("Running traditional quality checks...")
            results = {
                "resolution_check": self._check_resolution(pil_img), # Uses PIL
                "blur_check": self._check_blur(cv_img), # Uses OpenCV
                "brightness_check": self._check_brightness(cv_img), # Uses OpenCV
            }

            # Run OCR-based quality assessment
            logger.info("Running OCR-based quality assessment...")
            # Pass image_data (NumPy array) directly
            ocr_analysis = self._run_ocr(image_data)

            if "error" in ocr_analysis:
                 logger.error(f"OCR failed: {ocr_analysis['error']}")
                 results["ocr_quality"] = {
                     "pass": False,
                     "message": f"OCR processing failed: {ocr_analysis['error']}",
                     "average_confidence": 0.0
                 }
            else:
                avg_conf = ocr_analysis["average_confidence"]
                conf_pass = avg_conf >= self.ocr_min_confidence
                ocr_pass = conf_pass

                message = f"OCR Quality: Avg Conf {avg_conf:.2f} ({'OK' if conf_pass else 'LOW'})"
                if not ocr_pass:
                    message = f"Confidence too low ({avg_conf:.2f})"

                results["ocr_quality"] = {
                    "pass": ocr_pass,
                    "average_confidence": avg_conf,
                    "min_confidence_required": self.ocr_min_confidence,
                    "message": message
                }

            # Overall verdict
            results["pass"] = all(check["pass"] for check_name, check in results.items()
                                 if isinstance(check, dict) and "pass" in check)

            logger.info("Assessment completed successfully")
            return results

        except Exception as e:
            logger.exception(f"Unhandled error during assessment with direct data: {str(e)}")
            return {"status": "error", "message": f"Assessment failed: {str(e)}"}
    
    def _check_resolution(self, img):
        """Check if image resolution meets minimum requirements."""
        width, height = img.size
        min_width, min_height = self.min_resolution
        
        # Fix: Check if both dimensions are at least the minimum
        passes = width >= min_width and height >= min_height
        
        return {
            "pass": passes,
            "actual": (width, height),
            "required": self.min_resolution,
            "message": "Resolution OK" if passes else "Resolution too low"
        }
    
    def _check_blur(self, img):
        """Check image for blurriness using Laplacian variance."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        passes = laplacian_var >= self.blur_threshold
        
        return {
            "pass": passes,
            "value": laplacian_var,
            "threshold": self.blur_threshold,
            "message": "Image sharpness OK" if passes else "Image is too blurry"
        }
    
    def _check_brightness(self, img):
        """Check if image brightness is within acceptable range."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        brightness = hsv[:, :, 2].mean() / 255.0
        
        min_bright, max_bright = self.brightness_range
        passes = min_bright <= brightness <= max_bright
        
        return {
            "pass": passes,
            "value": brightness,
            "range": self.brightness_range,
            "message": "Brightness OK" if passes else 
                       "Image too dark" if brightness < min_bright else "Image too bright"
        }

# Usage example
if __name__ == "__main__":
    logger.info("Starting image quality assessment...")
    assessor = ImageQualityAssessor()
    
    # Test on a sample image
    sample_path = "Input/IMG_5063.png"
    logger.info(f"Testing with image: {sample_path}")
    
    if os.path.exists(sample_path):
        logger.info("Image file exists")
        results = assessor.assess_image(cv2.imread(sample_path))
        
        print("\nImage Quality Assessment Results:")
        print(f"Overall verdict: {'PASS' if results.get('pass', False) else 'FAIL'}")
        
        for check_name, result in results.items():
            if isinstance(result, dict) and "message" in result:
                status = "✓" if result.get("pass", False) else "✗"
                print(f"\n{status} {check_name}: {result['message']}")
                
                # Print additional details
                for key, value in result.items():
                    if key not in ["pass", "message"]:
                        print(f"  - {key}: {value}")
    else:
        logger.error(f"Sample image not found: {sample_path}")
        print(f"Sample image not found: {sample_path}")
