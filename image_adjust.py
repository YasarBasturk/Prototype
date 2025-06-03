import cv2
import numpy as np
import os

def adjust_brightness(image, factor):
    """
    Justerer billedets lysstyrke.
    Factor > 1.0 vil gøre billedet lysere.
    Factor < 1.0 vil gøre billedet mørkere.
    Factor = 1.0 er uændret.
    Factor = 0.5 svarer til 50% lysstyrke (mørkere).
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    v = np.clip(v * factor, 0, 255).astype(np.uint8) # Anvend faktor og klip til 0-255
    final_hsv = cv2.merge((h, s, v))
    img_bright_adjusted = cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)
    return img_bright_adjusted

def adjust_perspective(image, angle_deg_horizontal=0, angle_deg_vertical=0, scale=1.0):
    """
    Justerer billedets perspektiv for at simulere vinkling.
    angle_deg_horizontal: Vinkel i grader for horisontal "tilt" (positiv vipper toppen "væk").
    angle_deg_vertical: Vinkel i grader for vertikal "tilt" (positiv vipper venstre side "væk").
    """
    h, w = image.shape[:2]
    cx, cy = w // 2, h // 2

    # 1. Skalering (anvendes først for at undgå at vinkle et lille billede for meget)
    if scale != 1.0:
        scaled_image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        h, w = scaled_image.shape[:2] # Opdater dimensioner efter skalering
    else:
        scaled_image = image.copy()

    # Kilde-punkter (hjørner af det skalerbare billede)
    pts1 = np.float32([[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]])

    # Beregn forskydninger baseret på vinkler
    # Horisontal vinkling: Påvirker y-koordinaterne i toppen/bunden og x-koordinaterne for at skabe "dybde"
    # Positiv angle_deg_horizontal: toppen bliver "mindre" (ser længere væk ud)
    # Negativ angle_deg_horizontal: toppen bliver "større" (ser tættere på ud)
    horizontal_tilt_rad = np.deg2rad(angle_deg_horizontal)
    # For y: hvor meget toppen og bunden flyttes mod midten
    y_offset_top = (h / 2) * np.sin(horizontal_tilt_rad) * 0.5 # 0.5 for at dæmpe effekten
    # For x: hvor meget siderne "klemmes" ind i toppen/bunden
    x_squeeze_top_bottom = (w / 2) * (1 - np.cos(horizontal_tilt_rad)) * 0.5

    # Vertikal vinkling: Påvirker x-koordinaterne i siderne og y-koordinaterne for at skabe "dybde"
    # Positiv angle_deg_vertical: venstre side bliver "mindre"
    # Negativ angle_deg_vertical: venstre side bliver "større"
    vertical_tilt_rad = np.deg2rad(angle_deg_vertical)
    x_offset_left = (w / 2) * np.sin(vertical_tilt_rad) * 0.5
    y_squeeze_left_right = (h / 2) * (1 - np.cos(vertical_tilt_rad)) * 0.5

    pts2 = np.float32([
        [0 + x_offset_left + x_squeeze_top_bottom, 0 + y_offset_top + y_squeeze_left_right],  # Top-venstre
        [w - 1 - x_offset_left - x_squeeze_top_bottom, 0 + y_offset_top - y_squeeze_left_right], # Top-højre
        [0 + x_offset_left - x_squeeze_top_bottom, h - 1 - y_offset_top + y_squeeze_left_right], # Bund-venstre
        [w - 1 - x_offset_left + x_squeeze_top_bottom, h - 1 - y_offset_top - y_squeeze_left_right]  # Bund-højre
    ])

    matrix = cv2.getPerspectiveTransform(pts1, pts2)
    # Brug de oprindelige dimensioner før skalering til output, så billedet ikke bliver beskåret forkert hvis man skalerer ned
    original_h, original_w = image.shape[:2]
    warped_image = cv2.warpPerspective(scaled_image, matrix, (original_w, original_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))

    return warped_image

def adjust_blur(image, kernel_size):
    """
    Anvender Gaussian Blur på billedet.
    kernel_size skal være et ulige positivt heltal (f.eks. 3, 5, 15).
    Større kernel_size giver mere sløring.
    Hvis kernel_size er 0 eller 1, anvendes ingen sløring.
    """
    if kernel_size <= 1:
        return image
    # Sørg for at kernel_size er ulige
    if kernel_size % 2 == 0:
        kernel_size += 1
    blurred_image = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
    return blurred_image

def main():
    # --- MANUELLE PARAMETRE DU KAN ÆNDRE ---
    input_image_name = "IMG_5073.png"  # Skift til navnet på dit input billede
    output_image_name = "2.png" # Navn på output billede

    # Lysstyrke justering (1.0 = ingen ændring, 0.5 = 50% mørkere, 1.5 = 50% lysere)
    brightness_factor = 1.8 # Eksempel: 70% lysstyrke

    # Perspektiv/Vinkel justering
    # Vinkler i grader. Positive værdier "vipper" typisk den pågældende side væk.
    horizontal_tilt_degrees = 0 # Eksempel: Vip toppen 10 grader "væk"
    vertical_tilt_degrees = 0     # Eksempel: Vip venstre side 5 grader "væk"
    image_scale_factor = 1.0      # 1.0 = ingen skalering, 0.8 = 80% størrelse

    # Sløring justering (kernel size, skal være ulige, f.eks. 3, 5, 7 ... Større = mere sløret. 0 eller 1 = ingen sløring)
    blur_kernel_size = 0 # Eksempel: Moderat sløring
    # ------------------------------------------

    input_folder = "Input" 
    # Antager at 'Input' er en undermappe i samme mappe som scriptet
    # Hvis 'Input' er i rod-mappen af 'Prototype', skal du justere stien:
    # base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Går to niveauer op til Prototype
    # input_folder = os.path.join(base_dir, "Input")

    output_folder = "Output/Adjusted_Images" # Gemmer justerede billeder i en undermappe
    # Sørg for at output_folder også er relativ til scriptets placering eller en absolut sti
    # Hvis 'Output' skal være i rod-mappen:
    # output_folder = os.path.join(base_dir, "Output", "Adjusted_Images")

    # Opret output mappe hvis den ikke eksisterer
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Oprettet mappe: {output_folder}")

    input_path = os.path.join(input_folder, input_image_name)
    output_path = os.path.join(output_folder, output_image_name)

    # Indlæs billede
    original_image = cv2.imread(input_path)
    if original_image is None:
        print(f"Fejl: Kunne ikke indlæse billedet fra {input_path}")
        print("Kontroller om billednavnet er korrekt og om 'Input'-mappen findes hvor scriptet forventer det.")
        return

    print(f"Indlæst billede: {input_path}")
    processed_image = original_image.copy()

    # 1. Juster lysstyrke
    if brightness_factor != 1.0:
        print(f"Justerer lysstyrke med faktor: {brightness_factor}")
        processed_image = adjust_brightness(processed_image, brightness_factor)

    # 2. Juster perspektiv/vinkel (og skalering)
    if horizontal_tilt_degrees != 0 or vertical_tilt_degrees != 0 or image_scale_factor != 1.0:
        print(f"Justerer perspektiv/vinkel (H: {horizontal_tilt_degrees}°, V: {vertical_tilt_degrees}°, Scale: {image_scale_factor})")
        processed_image = adjust_perspective(processed_image, horizontal_tilt_degrees, vertical_tilt_degrees, image_scale_factor)

    # 3. Juster sløring
    if blur_kernel_size > 1 :
        print(f"Anvender sløring med kernel size: {blur_kernel_size}")
        processed_image = adjust_blur(processed_image, blur_kernel_size)

    # Gem det justerede billede
    cv2.imwrite(output_path, processed_image)
    print(f"Justeret billede gemt som: {output_path}")

    # (Valgfrit) Vis billederne
    # cv2.imshow("Original", original_image)
    # cv2.imshow("Justeret", processed_image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
