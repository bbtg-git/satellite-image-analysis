import io
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

import boto3
import pandas as pd
import streamlit as st
from PIL import Image, UnidentifiedImageError


st.set_page_config(page_title="Satellite Image Analysis", page_icon="🛰️", layout="wide")
st.title("🛰️ Satellite Image Analysis")
st.write(
    "Upload a ZIP of images or individual images. The app calculates basic image "
    "statistics, creates a CSV report, and can save the input and results to S3."
)

st.info(
    "Educational demo: green-pixel percentage is a simple RGB heuristic, "
    "not scientific vegetation classification or NDVI. True NDVI requires "
    "appropriate red and near-infrared band data."
)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def get_s3_client():
    """Create an S3 client using credentials from Streamlit secrets."""
    return boto3.client(
        "s3",
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=st.secrets["AWS_REGION"],
    )


def upload_to_s3(data: bytes, key: str, content_type: str):
    """Upload bytes to the configured private S3 bucket."""
    s3 = get_s3_client()
    s3.put_object(
        Bucket=st.secrets["S3_BUCKET"],
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def analyze_image(image_bytes: bytes, filename: str) -> dict:
    """Calculate basic RGB statistics for one image."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        pixels = list(rgb.getdata())

    total_pixels = len(pixels)
    red_avg = sum(pixel[0] for pixel in pixels) / total_pixels
    green_avg = sum(pixel[1] for pixel in pixels) / total_pixels
    blue_avg = sum(pixel[2] for pixel in pixels) / total_pixels

    # Simple RGB heuristic only; this is not NDVI.
    green_dominant = sum(
        1 for red, green, blue in pixels
        if green > red and green > blue
    )
    green_percentage = 100 * green_dominant / total_pixels

    return {
        "filename": filename,
        "width": width,
        "height": height,
        "pixel_count": total_pixels,
        "average_red": round(red_avg, 2),
        "average_green": round(green_avg, 2),
        "average_blue": round(blue_avg, 2),
        "green_dominant_pixel_percent": round(green_percentage, 2),
    }


def safe_zip_images(zip_bytes: bytes):
    """Extract supported image files from a ZIP without writing them to disk."""
    images = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            # Ignore folders and unsupported files.
            member_path = PurePosixPath(member.filename)
            if member_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            # Read the image bytes directly from the ZIP.
            images.append((member.filename, archive.read(member)))

    return images


st.subheader("Upload images")
zip_file = st.file_uploader("Upload a ZIP containing images", type=["zip"])
image_files = st.file_uploader(
    "Or select individual images",
    type=["png", "jpg", "jpeg", "tif", "tiff"],
    accept_multiple_files=True,
)

uploaded_images = []

if zip_file is not None:
    try:
        uploaded_images.extend(safe_zip_images(zip_file.getvalue()))
    except zipfile.BadZipFile:
        st.error("The uploaded file is not a valid ZIP archive.")

for image_file in image_files or []:
    uploaded_images.append((image_file.name, image_file.getvalue()))

# Avoid duplicate filenames from ZIP and individual uploads.
if uploaded_images:
    st.write(f"Images found: **{len(uploaded_images)}**")

    if st.button("Analyze images"):
        results = []
        input_objects = []

        progress = st.progress(0)
        status = st.empty()

        for index, (filename, image_bytes) in enumerate(uploaded_images, start=1):
            status.write(f"Analyzing {filename} ({index}/{len(uploaded_images)})")

            try:
                results.append(analyze_image(image_bytes, filename))
                input_objects.append((filename, image_bytes))
            except (UnidentifiedImageError, OSError, ValueError):
                st.warning(f"Skipped unreadable image: {filename}")

            progress.progress(index / len(uploaded_images))

        if results:
            report_df = pd.DataFrame(results)
            csv_bytes = report_df.to_csv(index=False).encode("utf-8")

            st.session_state["analysis_results"] = report_df
            st.session_state["analysis_csv"] = csv_bytes
            st.session_state["input_objects"] = input_objects

            status.success("Analysis complete.")
        else:
            st.error("No readable images were found.")

if "analysis_results" in st.session_state:
    report_df = st.session_state["analysis_results"]
    csv_bytes = st.session_state["analysis_csv"]

    st.subheader("Analysis results")
    st.dataframe(report_df, use_container_width=True)

    st.download_button(
        label="Download analysis CSV",
        data=csv_bytes,
        file_name="satellite_analysis_results.csv",
        mime="text/csv",
    )

    st.subheader("Save files to S3")
    st.caption(
        "Uploads original images under input/ and the CSV report under results/ "
        "in your configured bucket."
    )

    if st.button("Upload images and CSV to S3"):
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

            # Upload each successfully analyzed original image.
            for index, (filename, image_bytes) in enumerate(
                st.session_state["input_objects"], start=1
            ):
                safe_name = PurePosixPath(filename).name.replace(" ", "_")
                image_key = f"input/{timestamp}/{index}_{safe_name}"

                upload_to_s3(
                    image_bytes,
                    image_key,
                    "application/octet-stream",
                )

            # Upload the generated CSV report.
            csv_key = f"results/satellite_analysis_{timestamp}.csv"
            upload_to_s3(csv_bytes, csv_key, "text/csv")

            st.success(
                "Upload complete. Original images and the CSV report are saved "
                f"in bucket: {st.secrets['S3_BUCKET']}"
            )
            st.write(f"CSV object key: `{csv_key}`")

        except Exception as error:
            st.error(f"S3 upload failed: {error}")
else:
    st.warning("Upload a ZIP or individual images, then click **Analyze images**.")
