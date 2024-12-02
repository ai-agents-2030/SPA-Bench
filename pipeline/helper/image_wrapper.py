import os
import base64
import re


# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def generate_image_list(target_dir, slices=None, detail="high"):
    # Initialize an empty list to hold the dictionaries
    image_list = []

    # Function to extract the numerical part of the filename
    def extract_number(filename):
        match = re.search(r"(\d+)", filename)
        return int(match.group(0)) if match else float("inf")

    # Iterate over the image files in the specified folder
    for file_name in sorted(os.listdir(target_dir), key=extract_number):
        if not any(file_name.endswith(image_type) for image_type in ["jpg", "png"]):
            continue
        pic_path = os.path.join(target_dir, file_name)

        # Create the dictionary for each image
        image_dict = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encode_image(pic_path)}", "detail": detail},
        }

        # Append the dictionary to the list
        image_list.append(image_dict)
    # print(pic_path)

    if slices:
        # print(slices[0] - 1, slices[1])
        image_list = image_list[slices[0] - 1 : slices[1]]

    return image_list
