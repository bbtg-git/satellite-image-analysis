
import streamlit as st
import boto3
import numpy as np
import pandas as pd
from PIL import Image
from datetime import datetime
from io import BytesIO

st.set_page_config(
    page_title="Satellite Image Analysis",
    page_icon="🛰️",
    layout="wide"
)

BUCKET_NAME = "satellite-image-analysis-cc1"
REGION = "ap-south-1"

st.title("🛰️ Satellite Image Analysis")
st.write(
    "Upload a satellite image. The application automatically "
    "analyzes its basic pixel properties and stores the image "
    "and results in AWS S3."
)

def get_s3_client():
    return boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"]
    )

uploaded_file = st.file_uploader(
    "Upload satellite image",
    type=["png", "jpg", "jpeg", "tif", "tiff"]
)

if uploaded_file is not None:
    try:
        image_bytes = uploaded_file.getvalue()

        image = Image.open(BytesIO(image_bytes))
        image.load()

        image_array = np.asarray(image)

        st.success("Image uploaded successfully. Analysis started automatically.")

        left, right = st.columns(2)

        with left:
            st.subheader("Satellite Image")
            st.image(image, use_container_width=True)

        with right:
            st.subheader("Image Information")
            st.write("Filename:", uploaded_file.name)
            st.write("Image dimensions:", image.size)
            st.write("Image mode:", image.mode)
            st.write("Array shape:", image_array.shape)
            st.write("Data type:", str(image_array.dtype))

            st.subheader("Pixel Statistics")
            st.metric("Minimum pixel value", float(image_array.min()))
            st.metric("Maximum pixel value", float(image_array.max()))
            st.metric("Mean pixel value", round(float(image_array.mean()), 3))

        if image_array.ndim == 2:
            statistics = {
                "Band": ["Grayscale"],
                "Mean": [float(image_array.mean())],
                "Minimum": [int(image_array.min())],
                "Maximum": [int(image_array.max())]
            }
        else:
            channels = image_array.shape[2]
            names = ["Red", "Green", "Blue", "Alpha"]

            statistics = {
                "Band": [
                    names[i] if i < len(names) else f"Channel {i + 1}"
                    for i in range(channels)
                ],
                "Mean": [
                    float(image_array[:, :, i].mean())
                    for i in range(channels)
                ],
                "Minimum": [
                    int(image_array[:, :, i].min())
                    for i in range(channels)
                ],
                "Maximum": [
                    int(image_array[:, :, i].max())
                    for i in range(channels)
                ]
            }

        results = pd.DataFrame(statistics)

        st.subheader("Channel-wise Analysis")
        st.dataframe(results, use_container_width=True)

        with st.spinner("Saving image and analysis results to AWS S3..."):
            s3 = get_s3_client()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = uploaded_file.name.replace("/", "_").replace("\\", "_")

            image_key = f"input/{timestamp}_{safe_name}"
            results_key = f"output/{timestamp}_analysis.csv"

            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=image_key,
                Body=image_bytes
            )

            csv_bytes = results.to_csv(index=False).encode("utf-8")

            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=results_key,
                Body=csv_bytes,
                ContentType="text/csv"
            )

        st.success("Analysis completed and saved to AWS S3!")
        st.write("Image stored at:", image_key)
        st.write("Analysis stored at:", results_key)

    except Exception as error:
        st.error(f"Could not process this image: {error}")
