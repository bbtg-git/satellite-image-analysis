
import streamlit as st
import boto3
import numpy as np
from PIL import Image
from datetime import datetime
import io

st.set_page_config(
    page_title="Satellite Image Analysis",
    page_icon="🛰️",
    layout="wide"
)

BUCKET_NAME = "satellite-image-analysis-cc1"
REGION = "ap-south-1"

st.title("🛰️ Satellite Image Analysis")
st.subheader("Cloud-Based Geospatial Image Processing Platform")

st.info(
    "Upload a satellite image to inspect its dimensions, "
    "color channels and basic pixel statistics. "
    "Images are stored in your private AWS S3 bucket."
)

uploaded_file = st.file_uploader(
    "Upload satellite image",
    type=["png", "jpg", "jpeg", "tif", "tiff"]
)

if uploaded_file:
    try:
        image = Image.open(uploaded_file)
        image_array = np.array(image)

        st.subheader("Image Preview")

        if image_array.ndim == 2:
            st.image(image_array, caption="Grayscale image")
        else:
            st.image(image_array, caption="Satellite image")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Width", image.width, "pixels")

        with col2:
            st.metric("Height", image.height, "pixels")

        with col3:
            st.metric("Channels", 1 if image_array.ndim == 2
                      else image_array.shape[2])

        st.subheader("Image Statistics")

        st.write("Array shape:", image_array.shape)
        st.write("Pixel data type:", str(image_array.dtype))
        st.write("Minimum pixel value:", int(image_array.min()))
        st.write("Maximum pixel value:", int(image_array.max()))
        st.write("Mean pixel value:", round(float(image_array.mean()), 2))

        if st.button("Upload image to AWS S3"):
            session = boto3.Session(
                aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
                region_name=REGION
            )

            s3 = session.client("s3")

            uploaded_file.seek(0)

            extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

            object_key = (
                "input/satellite_image_"
                + datetime.now().strftime("%Y%m%d_%H%M%S")
                + "."
                + extension
            )

            s3.upload_fileobj(
                uploaded_file,
                BUCKET_NAME,
                object_key
            )

            st.success("Satellite image uploaded successfully!")
            st.write("S3 object:", object_key)

    except Exception as error:
        st.error(f"Processing error: {error}")
