import os
import logging
from io import BytesIO
from urllib.parse import unquote_plus

import boto3
from PIL import Image, ImageOps

s3 = boto3.client("s3")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]


def resize_image(bucket, key):
    # Keep original images and thumbnails in separate buckets.
    if bucket == OUTPUT_BUCKET:
        raise ValueError("The input and output buckets must be different.")

    # Read the original image from S3.
    response = s3.get_object(Bucket=bucket, Key=key)
    try:
        image_data = response["Body"].read()
    finally:
        response["Body"].close()

    # Correct orientation and resize without stretching the image.
    with Image.open(BytesIO(image_data)) as original:
        image = ImageOps.exif_transpose(original)
        image.thumbnail((200, 200))

        # PNG supports both regular images and transparent images.
        image = image.convert("RGBA")
        output = BytesIO()
        image.save(output, format="PNG")
        width, height = image.size

    # Preserve the original filename to avoid name collisions.
    output_key = "thumbnails/" + key + ".png"

    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_key,
        Body=output.getvalue(),
        ContentType="image/png"
    )

    logger.info("Thumbnail saved: %s", output_key)

    return {
        "bucket": OUTPUT_BUCKET,
        "key": output_key,
        "width": width,
        "height": height
    }


def lambda_handler(event, context):
    # S3 uploads send a list of event records.
    if "Records" in event:
        results = []

        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
            results.append(resize_image(bucket, key))

        return {"success": True, "images": results}

    # Tests and Step Functions supply a bucket and an image key.
    try:
        result = resize_image(event["bucket"], event["key"])
        return {"success": True, "image": result}

    except Exception:
        logger.exception("Image resizing failed")
        return {
            "success": False,
            "message": "Image resizing failed. Check CloudWatch logs."
        }
