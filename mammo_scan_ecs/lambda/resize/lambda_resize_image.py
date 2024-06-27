import json
import cv2
import boto3
import numpy as np


s3 = boto3.client('s3')
sagemaker = boto3.client('runtime.sagemaker')
lambda_client = boto3.client('lambda')

original_path = "downloaded/original"
resized_path = "downloaded/resized"


def lambda_handler(event, context):
       
    IMAGE_FILE = event['filename']
    bucket = event['bucket']

    try:
        s3_object = s3.get_object(Bucket=bucket, Key="{}/{}".format(original_path, IMAGE_FILE))
        s3_object_byte_array = s3_object['Body'].read()

        # creating 1D array from bytes data range between[0,255]
        np_array = np.fromstring(s3_object_byte_array, np.uint8)

        # decoding array
        s3_object_imdecode = cv2.imdecode(np_array, cv2.IMREAD_UNCHANGED)

        resized_image = cv2.resize(
            s3_object_imdecode, (150, 300), interpolation=cv2.INTER_AREA)
       
        # saving image to tmp (writable) directory    
        print("ResizeMammography.tmp_file_name = " + IMAGE_FILE)
        cv2.imwrite(IMAGE_FILE, resized_image)

        # uploading converted image to S3 bucket
        s3.put_object(Bucket=bucket, Key="{}/{}".format(resized_path, IMAGE_FILE),
                      Body=open("/tmp/"+ IMAGE_FILE, "rb").read())

        result = {
            "bucket": bucket,
            "key": "{}/{}".format(resized_path, IMAGE_FILE)
        }
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        print(e)
        raise e