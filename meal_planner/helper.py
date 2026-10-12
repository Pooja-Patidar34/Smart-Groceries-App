import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import requests
from django.utils import timezone



def download_and_save_image(image_url, filename_prefix="recipe_image"):
    try:
        image_data = requests.get(image_url).content
        filename = f"{filename_prefix}_{timezone.now().timestamp()}.png"
        path = os.path.join("recipes", filename)  # media/recipes/filename.png
        saved_path = default_storage.save(path, ContentFile(image_data))
        return default_storage.url(saved_path)  # returns media URL
    except Exception as e:
        print(f"Error saving image: {e}")
        return None
