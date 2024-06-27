#!/usr/bin/env python3
import sagemaker

import aws_cdk as cdk
from aws_cdk import (
    Aws
)

from datetime import datetime

from mammo_scan_ecs.mammo_scan_ecs_stack import MammoScanEcsStack
from mammo_scan_ecs.vpc_stack import MammoScanVpcStack
from mammo_scan_ecs.frontend_stack import FrontEndWebStack
from mammo_scan_ecs.sagemaker_stack import SageMakerStack

env = {
      'region': Aws.REGION
    }

endpoint_name = 'mammography-classification-endpoint'

image_uri = sagemaker.image_uris.retrieve(
    region="us-east-1",
    framework="image-classification")

hyperparameters={
            "num_layers": "18",
            "image_shape": "3,300,150",
            "num_classes": "5",
            "num_training_samples": "1752",
            "mini_batch_size": "120",
            "epochs": "20",
            "learning_rate": "0.01",
            "optimizer": "sgd",
            "top_k": "2",
            "precision_dtype": "float32"
        }

sagemaker_configs = {
    "hyperparameters": hyperparameters,
    "image_uri": image_uri,
    "endpoint_name": endpoint_name,
    "training_instance_type": "p3.2xlarge",
    "inference_instance_type": "m5.large",
}




app = cdk.App()
# MammoScanEcsStack(app, "MammoScanEcsStack")
vpc_network = MammoScanVpcStack(app, "MammoScanVpcStack")

FrontEndWebStack(app, "FrontEndWebStack", vpc=vpc_network.get_vpc, sagemaker_configs=sagemaker_configs, env=env)

SageMakerStack(app, "SagemakerStack", sagemaker_configs=sagemaker_configs, env=env)


app.synth()
