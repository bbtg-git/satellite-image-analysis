import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from pathlib import PurePosixPath

st.set_page_config(
    page_title="Satellite Image Analysis",
    page_icon="🛰️",
    layout="wide",
)

st.title("🛰️ Satellite Image Analysis")
st.write(
    "Upload a ZIP containing your dataset folders, or select individual images. "
    "The app summarizes each image and creates a downloadable CSV report."
)

st.info(
    "Educational demo: the green-pixel estimate is a simple RGB heuristic, "
    "not scientific vegetation classification or NDVI. True NDVI requires red "
    "and near-infrared (NIR) band data."
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def analyze_image(image_bytes):
    """Calculate basic image statistics from an image."""
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    pixels = np.asarray(image, dtype=np.uint8)

    red = pixels[:, :, 0].astype(np.int16)
    green = pixels[:, :, 1].astype(np.int16)
    blue = pixels[:, :, 2].astype(np.int16)

    green_dominant = (
        (green > red * 1.10)
        & (green > blue * 1.05)
        & (green > 40)
    )

    return {
        "image": image,
        "width": image.width,
        "height": image.height,
        "pixel_count": image.width * image.height,
        "mean_red": round(float(red.mean()), 2),
        "mean_green": round(float(green.mean()), 2),
        "mean_blue": round(float(blue.mean()), 2),
        "green_dominant_percent": round(float(green_dominant.mean() * 100), 2),
    }


def images_from_zip(zip_file):
    """Read supported images from a ZIP without extracting them to disk."""
    image_items = []

    try:
        with ZipFile(zip_file) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue

                path = PurePosixPath(entry.filename)

                # Ignore hidden files and common macOS ZIP metadata.
                if any(part.startswith(".") for part in path.parts):
                    continue
                if "__MACOSX" in path.parts:
                    continue
                if path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                # The first folder inside the ZIP is used as the class/category.
                category = path.parent.name if path.parent.name else "Uncategorized"

                image_items.append({
                    "filename": path.name,
                    "relative_path": entry.filename,
                    "category": category,
                    "bytes": archive.read(entry),
                })

    except BadZipFile:
        st.error("That file is not a valid ZIP archive.")
        return []

    return image_items


zip_upload = st.file_uploader(
    "Upload your dataset as a ZIP file",
    type=["zip"],
    help="ZIP your dataset folder so its class folders (Forest, AnnualCrop, etc.) are inside it.",
)

individual_uploads = st.file_uploader(
    "Or select individual images",
    type=["png", "jpg", "jpeg", "tif", "tiff"],
    accept_multiple_files=True,
    key="individual_images",
)

image_items = []

if zip_upload is not None:
    image_items.extend(images_from_zip(zip_upload))

if individual_uploads:
    for uploaded_file in individual_uploads:
        image_items.append({
            "filename": uploaded_file.name,
            "relative_path": uploaded_file.name,
            "category": "Individual upload",
            "bytes": uploaded_file.getvalue(),
        })

if image_items:
    st.write(f"Found **{len(image_items)}** image(s) to analyze.")

    results = []
    preview_columns = st.columns(2)

    for index, item in enumerate(image_items):
        try:
            stats = analyze_image(item["bytes"])

            results.append({
                "filename": item["filename"],
                "relative_path": item["relative_path"],
                "category": item["category"],
                "width": stats["width"],
                "height": stats["height"],
                "pixel_count": stats["pixel_count"],
                "mean_red": stats["mean_red"],
                "mean_green": stats["mean_green"],
                "mean_blue": stats["mean_blue"],
                "green_dominant_percent": stats["green_dominant_percent"],
            })

            # Show a small preview of the first few images.
            if index < 4:
                with preview_columns[index % 2]:
                    st.image(
                        stats["image"],
                        caption=f"{item['category']} / {item['filename']}",
                        use_container_width=True,
                    )
                    st.caption(
                        f"{stats['width']} × {stats['height']} pixels · "
                        f"Green-dominant: {stats['green_dominant_percent']}%"
                    )

        except (UnidentifiedImageError, OSError, ValueError) as error:
            st.warning(f"Could not read {item['relative_path']}: {error}")

    if results:
        results_df = pd.DataFrame(results)

        st.subheader("Analysis summary")
        st.dataframe(results_df, use_container_width=True)

        csv_data = results_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download analysis as CSV",
            data=csv_data,
            file_name="satellite_image_analysis.csv",
            mime="text/csv",
        )

else:
    st.warning("Upload a ZIP dataset or select individual images to begin.")
