import boto3
import json
import os
from datetime import datetime

sfn_client = boto3.client('stepfunctions')
prefix = 'resize'
bucket = 'mammo-v2-ecs-model-files'
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']



# Four channels: train, validation, train_lst, and validation_lst
s3train = 's3://{}/{}/train/'.format(bucket, prefix)
s3validation = 's3://{}/{}/test/'.format(bucket, prefix)
s3train_lst = 's3://{}/{}/train-data.lst'.format(bucket, prefix)
s3validation_lst = 's3://{}/{}/test-data.lst'.format(bucket, prefix)
job_name = 'mammography-classification-' + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
prefix_output='model/output'
s3_output_location = 's3://{}/{}'.format(bucket, prefix_output)


def lambda_handler(event, context):
   
    statemachine_payload = {
        "smJobName": job_name,              
        "s3train": s3train,          
        "s3validation": s3validation,
        "s3train_lst": s3train_lst,
        "s3validation_lst": s3validation_lst,
        "s3_output_location": s3_output_location,     
    }
 
    response = sfn_client.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input= json.dumps(statemachine_payload)
    )
    print(response)

    return {
        'statusCode': 200,
        'body': json.dumps('State machine has been started')
    }