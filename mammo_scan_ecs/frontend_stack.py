from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_ec2 as ec2,    
    aws_iam as iam,
    aws_ssm as ssm,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
)
from constructs import Construct

class FrontEndWebStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.IVpc, sagemaker_configs, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        endpoint_name = sagemaker_configs["endpoint_name"]

        # Defines role for the AWS Lambda functions
        role = iam.Role(self, "Mammography-Lambda-Policy", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"))
        role.attach_inline_policy(iam.Policy(self, "sm-invoke-policy",
            statements=[iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sagemaker:InvokeEndpoint"],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter"],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:*"],
                resources=["*"]
            )]
        ))

        cv2_layer = _lambda.LayerVersion(    
            self, "opencv-layer",
            code=_lambda.Code.from_asset("./lambda_layers/opencv.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
        )

        numpy_layer = _lambda.LayerVersion(
            self, "numpy-layer",
            code=_lambda.Code.from_asset("./lambda_layers/numpy.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
        )

        classification_lambda = _lambda.Function(self, "classification-lambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="lambda_invoke_classifier.lambda_handler",
            code=_lambda.Code.from_asset("./mammo_scan_ecs/lambda/classify"),
            role=role,
            layers=[cv2_layer, numpy_layer],
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={
                "ENDPOINT_NAME": endpoint_name
            }
        )

        resize_img_lambda = _lambda.Function(
            self, "ResizeImgLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("./mammo_scan_ecs/lambda/resize"),
            handler="lambda_resize_image.lambda_handler",
            role=role,
            layers=[cv2_layer, numpy_layer],
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            timeout=Duration.seconds(120),
        )

        api = apigw.LambdaRestApi(
            self, 'Endpoint',
            handler=classification_lambda,
            rest_api_name='Mammography Classification'
        )


        # Create ECS cluster
        cluster = ecs.Cluster(self, "MammographyClassification", vpc=vpc)

        # Add an AutoScalingGroup with spot instances to the existing cluster
        cluster.add_capacity("AsgSpot",
            max_capacity=2,
            min_capacity=1,
            desired_capacity=2,
            instance_type=ec2.InstanceType("c5.xlarge"),
            spot_price="0.0735",
            # Enable the Automated Spot Draining support for Amazon ECS
            spot_instance_draining=True
        )

        # Build Dockerfile from local folder and push to ECR
        image = ecs.ContainerImage.from_asset("web-app")

        # Create Fargate service
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "MammographyApplication",
            cluster=cluster,            # Required
            cpu=2048,                   # Default is 256 (512 is 0.5 vCPU, 2048 is 2 vCPU)
            desired_count=1,            # Default is 1
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=image, 
                container_port=8501,
                ),
            #load_balancer_name="gen-ai-demo",
            memory_limit_mib=4096,      # Default is 512
            public_load_balancer=True)  # Default is True

        fargate_service.task_definition.add_to_task_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions = ["ssm:GetParameter"],
            resources = ["arn:aws:ssm:*"],
            )
        )

        fargate_service.task_definition.add_to_task_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions = [
                "execute-api:Invoke",
                "execute-api:ManageConnections"
            ],
            resources = ["*"],
            )
        )

        # Setup task auto-scaling
        scaling = fargate_service.service.auto_scale_task_count(
            max_capacity=10
        )
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=50,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )  


            
        ssm.StringParameter(
            self, "ParamResizeImg",
            parameter_name="resize-img-endpoint",
            string_value=api.url,
        )
        ssm.StringParameter(
            self, "ResizeLambda",
            parameter_name="resize-lambda",
            string_value=resize_img_lambda.function_name,
        )
        ssm.StringParameter(
            self, "ClassificationLambda",
            parameter_name="classify-lambda",
            string_value=classification_lambda.function_name,
        )