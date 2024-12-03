import os
import json
import shutil
from PIL import Image, ImageDraw, ImageFont
import textwrap


def draw_tap_action(image_path, coordinates, output_path):
    # Open the image
    image = Image.open(image_path).convert("RGBA")

    # Create a transparent layer for drawing the dot
    dot_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(dot_layer)

    # Define the red dot properties
    dot_radius = 20
    dot_color = (255, 0, 0, 128)  # Red color with transparency (128 out of 255)

    # Calculate the bounding box for the dot
    x, y = coordinates
    left_up_point = (x - dot_radius, y - dot_radius)
    right_down_point = (x + dot_radius, y + dot_radius)

    # Draw the red dot on the transparent layer
    draw.ellipse([left_up_point, right_down_point], fill=dot_color)

    # Composite the dot layer onto the original image
    combined_image = Image.alpha_composite(image, dot_layer)

    # Save the combined image
    combined_image.save(output_path, "PNG")


def calculate_characters_per_line(image_width, font):
    # Measure the width of a sample of characters
    sample_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    total_width = sum([font.getbbox(char)[2] - font.getbbox(char)[0] for char in sample_text])
    average_char_width = total_width / len(sample_text)

    # Calculate the number of characters that fit in one line
    characters_per_line = image_width // average_char_width
    return int(characters_per_line)


def add_strip_with_text(image_path, text_segments, output_path, font_size=60, line_spacing=10):
    # Open the original image
    image = Image.open(image_path)
    width, height = image.size

    # Prepare to draw text
    draw = ImageDraw.Draw(image)
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to the file
    font_path = os.path.join(script_dir, "NotoSansCJK-Regular.ttc")
    font = ImageFont.truetype(font_path, font_size)

    ## Calculate characters per line
    characters_per_line = calculate_characters_per_line(width, font)

    # Wrap each line to fit within the image width
    wrapped_lines = []
    for segment in text_segments:
        color = segment["color"]
        for line in segment["text"].split("\n"):
            wrapped_lines.append(
                {"text": textwrap.wrap(line, width=characters_per_line), "color": color}
            )  # Adjust width parameter as needed

    # Calculate the size of the text block
    text_height = 0
    for wrapped_segment in wrapped_lines:
        for line in wrapped_segment["text"]:
            text_bbox = draw.textbbox((0, 0), line, font=font)
            text_height += text_bbox[3] - text_bbox[1] + line_spacing

    # Calculate new height for the image with the strip and the blue line
    strip_height = text_height + 20  # Adding some padding
    blue_line_height = 10  # Height of the blue line
    new_height = height + blue_line_height + strip_height

    # Create a new image with a white strip and a blue line at the bottom
    new_image = Image.new("RGB", (width, new_height), "white")
    new_image.paste(image, (0, 0))

    # Prepare to draw on the new image
    draw = ImageDraw.Draw(new_image)

    # Draw the blue line
    draw.rectangle([(0, height), (width, height + blue_line_height)], fill="blue")

    # Calculate the position for the text to be centered
    y_text = height + blue_line_height + 10  # Start position with padding after the blue line
    for wrapped_segment in wrapped_lines:
        color = wrapped_segment["color"]
        for line in wrapped_segment["text"]:
            text_bbox = draw.textbbox((0, 0), line, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = (width - text_width) // 2
            draw.text((text_x, y_text), line, font=font, fill=color)
            y_text += text_bbox[3] - text_bbox[1] + line_spacing

    # Save the new image
    new_image.save(output_path)


def wrap_action_text(action, action_detail):
    text_segments = [
        {"text": "Action:", "color": "red"},
        {"text": action, "color": "black"},
        {"text": "\nDetail:", "color": "red"},
        {"text": action_detail, "color": "black"},
    ]
    return text_segments


def process_images(folder_path, text_info=True):
    # Load the log.json
    with open(os.path.join(folder_path, "log.json"), encoding="utf-8") as file:
        log = json.load(file)

    # Determine the number of images in the folder
    image_files = [f for f in os.listdir(folder_path) if f.endswith((".png", ".jpg"))]
    num_images = len(image_files)

    # Add tap red dot info
    # Create a new directory for the modified images
    output_folder_tap = os.path.join(folder_path, "tap_only")
    if os.path.exists(output_folder_tap):
        shutil.rmtree(output_folder_tap)
    os.makedirs(output_folder_tap)
    # Process each image
    for step in range(1, num_images):
        input_image = os.path.join(folder_path, f"{step-1}.png")
        output_image = os.path.join(output_folder_tap, f"{step-1}.png")
        # Copy the original image to the new folder
        shutil.copy(input_image, output_image)
        if len(log) > step - 1 and "action" in log[step - 1]:
            action = log[step - 1]["action"]
            detail_type = action[1]["detail_type"]
            detail = action[1]["detail"]
            coordinates = detail
            if detail_type == "coordinates":
                # Draw the tap action on the copied image
                draw_tap_action(output_image, coordinates, output_image)
    # Copy the final image to the new folder
    final_image_input = os.path.join(folder_path, f"{num_images-1}.png")
    final_image_output = os.path.join(output_folder_tap, f"{num_images-1}.png")
    shutil.copy(final_image_input, final_image_output)

    # Add text info
    if text_info:
        # Create a new directory for the modified images
        output_folder_text = os.path.join(folder_path, "tap_and_text")
        if os.path.exists(output_folder_text):
            shutil.rmtree(output_folder_text)
        os.makedirs(output_folder_text)
        # Process each image
        for step in range(1, num_images):
            input_image = os.path.join(output_folder_tap, f"{step-1}.png")
            output_image = os.path.join(output_folder_text, f"{step-1}.png")
            # Copy the original image to the new folder
            shutil.copy(input_image, output_image)
            if len(log) > step - 1 and "action" in log[step - 1]:
                action = log[step - 1]["action"]
                detail_type = action[1]["detail_type"]
                detail = action[1]["detail"]
                coordinates = detail
                if detail_type == "coordinates":
                    detail = "The red dot was acted upon."
                # Add the text info on the copied image
                text_segments = wrap_action_text(action[0], detail)
                add_strip_with_text(output_image, text_segments, output_image)
        # Copy the final image to the new folder
        final_image_input = os.path.join(output_folder_tap, f"{num_images-1}.png")
        final_image_output = os.path.join(output_folder_text, f"{num_images-1}.png")
        shutil.copy(final_image_input, final_image_output)
