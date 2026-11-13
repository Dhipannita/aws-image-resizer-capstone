# AWS Image Resizer Capstone

## Project Overview

For this assignment, I created an image resizing application using AWS.

When a JPG image is uploaded to the originals S3 bucket, Lambda automatically resizes it and saves a smaller PNG image in the thumbnails bucket.

I also created a Step Functions workflow to run Lambda and check the result. API Gateway allows the workflow to start through a POST request.

## AWS Services Used

- Amazon S3 stores the original images and thumbnails.
- AWS Lambda resizes the images using Python and Pillow.
- AWS Step Functions runs Lambda and checks whether processing succeeded.
- Amazon API Gateway starts the workflow.
- AWS IAM provides the permissions needed by each service.

## Project Files

- `lambda_function.py`: Python code for resizing images.
- `state_machine.json`: Step Functions workflow definition.
- `README.md`: Project setup and testing instructions.

## Setup

### 1. S3 Buckets

I created two buckets in Canada Central (`ca-central-1`):

- `dhipannita-capstone-originals-20261112`
- `dhipannita-capstone-thumbnails-20261112`

Public access is blocked for both buckets. Keeping the original images and thumbnails in separate buckets prevents the output images from triggering the same process again.

### 2. Lambda Function

I created a Lambda function named `CapstoneResizeImage` with these settings:

| Setting | Value |
| --- | --- |
| Runtime | Python 3.12 |
| Architecture | x86_64 |
| Memory | 512 MB |
| Timeout | 30 seconds |
| Handler | `lambda_function.lambda_handler` |

The function uses the code in `lambda_function.py`.

I added the environment variable `OUTPUT_BUCKET` with the value `dhipannita-capstone-thumbnails-20261112`.

The Lambda execution role has permission to:
- Read objects from the originals bucket using `s3:GetObject`.
- Save objects in the thumbnails bucket using `s3:PutObject`.
- Write logs to CloudWatch.

### 3. Pillow Layer

I used Pillow to resize the images. I ran these commands in AWS CloudShell to create the Lambda layer:

```bash
mkdir -p ~/capstone-pillow/python
cd ~/capstone-pillow

python3 -m pip install Pillow --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --target python

zip -qr pillow-layer.zip python

aws lambda publish-layer-version --layer-name CapstonePillow --zip-file fileb://pillow-layer.zip --compatible-runtimes python3.12 --compatible-architectures x86_64 --region ca-central-1 --query LayerVersionArn --output text
```

I attached the `CapstonePillow` layer to the Lambda function and deployed the code.

### 4. S3 Trigger

I added an S3 trigger to the Lambda function with these settings:

- Bucket: `dhipannita-capstone-originals-20261112`
- Event: All object create events
- Suffix: `.jpg`

An upload with a lowercase `.jpg` filename automatically starts the function.

The function resizes the image to fit within 200 × 200 pixels while keeping its original proportions. It saves the result as a PNG in the `thumbnails/` folder of the output bucket.

### 5. Step Functions Workflow

I created a Standard state machine named `CapstoneImageWorkflow` using the definition in `state_machine.json`.

The workflow contains four states:

| State | Purpose |
| --- | --- |
| `ResizeImage` | Runs the Lambda function |
| `CheckResizeResult` | Checks the success value returned by Lambda |
| `ProcessingSucceeded` | Ends a successful execution |
| `ProcessingFailed` | Ends a failed execution |

The state machine execution role has permission to invoke `CapstoneResizeImage`.

### 6. API Gateway

I created a Regional REST API named `CapstoneImageAPI` with a `POST /resize` method.

The integration settings are:

| Setting | Value |
| --- | --- |
| Integration type | AWS service |
| Region | `ca-central-1` |
| Service | Step Functions |
| Integration HTTP method | POST |
| Action | `StartExecution` |
| Execution role | `CapstoneApiGatewayRole` |

The API Gateway role allows API Gateway to assume it and start the project state machine using `states:StartExecution`.

I added this integration request mapping template with the content type `application/json`:

```json
{
  "stateMachineArn": "arn:aws:states:ca-central-1:956646644848:stateMachine:CapstoneImageWorkflow",
  "input": "$util.escapeJavaScript($input.body).replaceAll("\\'","'")"
}
```

I deployed the API to the `dev` stage.

The endpoint is:

```text
https://3lokwb95ff.execute-api.ca-central-1.amazonaws.com/dev/resize
```

For deployment in another AWS account, the bucket names, resource ARNs and API URL must be updated.

## Running and Testing the Application

### Automatic S3 Upload

1. Upload a JPG image to the originals bucket.
2. Open the thumbnails bucket.
3. Check the `thumbnails/` folder for the resized PNG.
4. Download the thumbnail to check its dimensions.

I tested this with `Flower2.jpg`. The output was `thumbnails/Flower2.jpg.png`, with dimensions of 113 × 200 pixels.

### Successful Workflow Test

Start an execution of `CapstoneImageWorkflow` with this input:

```json
{
  "bucket": "dhipannita-capstone-originals-20261112",
  "key": "Flower2.jpg"
}
```

My test finished with the status `Succeeded`.

### Failed Workflow Test

Start another execution with a filename that does not exist:

```json
{
  "bucket": "dhipannita-capstone-originals-20261112",
  "key": "missing-image.jpg"
}
```

My test reached `ProcessingFailed` and returned the error `ImageProcessingFailed`, as expected.

### Deployed API Test

Run this command in AWS CloudShell:

```bash
curl -i -X POST 'https://3lokwb95ff.execute-api.ca-central-1.amazonaws.com/dev/resize' -H 'Content-Type: application/json' -d '{"bucket":"dhipannita-capstone-originals-20261112","key":"Flower2.jpg"}'
```

The API returned HTTP `200` with an `executionArn`.

HTTP `200` confirms that the workflow started. I checked the matching execution in Step Functions and confirmed that it finished with the status `Succeeded`.

## Test Results

| Test | Result |
| --- | --- |
| Direct Lambda test | Thumbnail created |
| Automatic S3 upload test | Thumbnail created automatically |
| Workflow with an existing image | Succeeded |
| Workflow with a missing image | Failed as expected |
| API Gateway console test | HTTP 200 and successful workflow |
| Deployed API test using curl | HTTP 200 and successful workflow |
