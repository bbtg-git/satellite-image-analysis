import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = "satellite-image-analysis-cc1"
REGION = "ap-south-1"

# Use AWS credentials from your configured CLI profile
session = boto3.Session(
    profile_name="cloud-project",
    region_name=REGION
)

s3 = session.client("s3")

try:
    s3.head_bucket(Bucket=BUCKET_NAME)
    print("SUCCESS: Connected to Geo Science S3 bucket!")

    # Upload a test file
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key="input/test.txt",
        Body=b"Geo Science project connected successfully!"
    )

    print("SUCCESS: Test file uploaded!")

    # List files in the input folder
    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix="input/"
    )

    for obj in response.get("Contents", []):
        print("File:", obj["Key"])

except ClientError as error:
    print("AWS ERROR:", error)
