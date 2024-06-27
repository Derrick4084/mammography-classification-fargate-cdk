import random
from aws_cdk import (
    Duration,
    Size,
    Aws,
    aws_ssm as ssm,
    aws_ec2 as ec2,
    aws_iam as _iam,
    aws_logs as logs,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    Stack,
    RemovalPolicy,
)
from constructs import Construct

class SageMakerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, sagemaker_configs, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        HYPER_PARAMS = sagemaker_configs["hyperparameters"]
        IMAGE_URI = sagemaker_configs["image_uri"]
        ENDPOINT_NAME = sagemaker_configs["endpoint_name"]
        TRN_INSTANCE_TYPE = sagemaker_configs["training_instance_type"]
        INFERENCE_INSTANCE_TYPE = sagemaker_configs["inference_instance_type"]

        random_number = random.randint(1000, 2000)   

        tasks_execution_role = _iam.Role(self, "sagemaker-execution-role",
            assumed_by=_iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                _iam.ManagedPolicy.from_aws_managed_policy_name("AWSStepFunctionsFullAccess"),
                _iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
            ],
            inline_policies={
                "s3_access": _iam.PolicyDocument(statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:*"],
                        resources=["arn:aws:s3:::*/*"]
                    )
                ])},
            role_name="sagemaker-execution-role"
         )
        training_job_task = tasks.SageMakerCreateTrainingJob(self, "CreateTrainingJob",
            algorithm_specification=tasks.AlgorithmSpecification(
                training_image=tasks.DockerImage.from_registry(IMAGE_URI),
                training_input_mode=tasks.InputMode.FILE
            ),
            input_data_config=[tasks.Channel(
                channel_name="train",
                data_source=tasks.DataSource(
                    s3_data_source=tasks.S3DataSource(
                        s3_data_distribution_type=tasks.S3DataDistributionType.FULLY_REPLICATED,
                        s3_data_type=tasks.S3DataType.S3_PREFIX,
                        s3_location=tasks.S3Location.from_json_expression("$.s3train")
                    )
                ),
                content_type="application/x-image"
            ),
            tasks.Channel(
                channel_name="validation",
                data_source=tasks.DataSource(
                    s3_data_source=tasks.S3DataSource(
                        s3_data_distribution_type=tasks.S3DataDistributionType.FULLY_REPLICATED,
                        s3_data_type=tasks.S3DataType.S3_PREFIX,
                        s3_location=tasks.S3Location.from_json_expression("$.s3validation")
                    )
                ),
                content_type="application/x-image"
            ),
            tasks.Channel(
                channel_name="train_lst",
                data_source=tasks.DataSource(
                    s3_data_source=tasks.S3DataSource(
                        s3_data_distribution_type=tasks.S3DataDistributionType.FULLY_REPLICATED,
                        s3_data_type=tasks.S3DataType.S3_PREFIX,
                        s3_location=tasks.S3Location.from_json_expression("$.s3train_lst")
                    )
                ),
                content_type="application/x-image"
            ),
            tasks.Channel(
                channel_name="validation_lst",
                data_source=tasks.DataSource(
                    s3_data_source=tasks.S3DataSource(
                        s3_data_distribution_type=tasks.S3DataDistributionType.FULLY_REPLICATED,
                        s3_data_type=tasks.S3DataType.S3_PREFIX,
                        s3_location=tasks.S3Location.from_json_expression("$.s3validation_lst")
                    )
                ),
                content_type="application/x-image"
            )
            ],
            output_data_config=tasks.OutputDataConfig(
                s3_output_location=tasks.S3Location.from_json_expression("$.s3_output_location")
            ),
            training_job_name=sfn.JsonPath.string_at("$.smJobName"),
            hyperparameters=HYPER_PARAMS,
            role=tasks_execution_role,           
            resource_config=tasks.ResourceConfig(
                instance_count=1,
                instance_type=ec2.InstanceType(TRN_INSTANCE_TYPE),
                volume_size=Size.gibibytes(20)
            ),
            stopping_condition=tasks.StoppingCondition(
                max_runtime=Duration.hours(2)
            ),
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            result_path= "$.TrainJobResults",
            result_selector={ 
                "ModelName.$": "$.TrainingJobName",
                "ModelArtifacts.$": "$.ModelArtifacts.S3ModelArtifacts"
             },
            task_timeout=sfn.Timeout.duration(Duration.minutes(60)),
            # state_name="Train Model"           
        )


        create_model_task = tasks.SageMakerCreateModel(self, "CreateModel",
            model_name=sfn.JsonPath.string_at("$.TrainJobResults.ModelName"),
            primary_container=tasks.ContainerDefinition(
                image=tasks.DockerImage.from_registry(IMAGE_URI),
                model_s3_location=tasks.S3Location.from_json_expression("$.TrainJobResults.ModelArtifacts")
            ),
            role=tasks_execution_role,
            integration_pattern=sfn.IntegrationPattern.REQUEST_RESPONSE,
            result_path="$.CreateModelResults",
            result_selector={
                "HttpStatusCode.$": "$.SdkHttpMetadata.HttpStatusCode",
                "ModelArn.$": "$.ModelArn"
            },
            task_timeout=sfn.Timeout.duration(Duration.minutes(10)),
            # state_name="Save Model"

        )

        endpoint_config_task = tasks.SageMakerCreateEndpointConfig(self, "CreateEndpointConfig",
            endpoint_config_name=sfn.JsonPath.string_at("$.TrainJobResults.ModelName"),
            production_variants=[tasks.ProductionVariant(
                initial_instance_count=1,
                instance_type=ec2.InstanceType(INFERENCE_INSTANCE_TYPE),
                model_name=sfn.JsonPath.string_at("$.TrainJobResults.ModelName"),
                variant_name="AllTraffic",

            )],
            integration_pattern=sfn.IntegrationPattern.REQUEST_RESPONSE,
            result_path="$.CreateEndpointConfigResults",
            result_selector={
                "HttpStatusCode.$": "$.SdkHttpMetadata.HttpStatusCode",
                "EndpointConfigArn.$": "$.EndpointConfigArn"
            },
            task_timeout=sfn.Timeout.duration(Duration.minutes(10)),
            # state_name="Create Endpoint Config"
        )

        create_endpoint_task = tasks.SageMakerCreateEndpoint(
            self, "CreateEndpoint",
            endpoint_config_name=sfn.JsonPath.string_at("$.TrainJobResults.ModelName"),
            endpoint_name=ENDPOINT_NAME,
            integration_pattern=sfn.IntegrationPattern.REQUEST_RESPONSE,
            result_path="$.CreateEndpointResults",
            result_selector={
                "HttpStatusCode.$": "$.SdkHttpMetadata.HttpStatusCode",
                "EndpointArn.$": "$.EndpointArn"
            },
            task_timeout=sfn.Timeout.duration(Duration.minutes(10)),
            # state_name="Create Endpoint"
        )


        state_machine_role = _iam.Role(self, "StateMachineExecutionRole",
            assumed_by=_iam.ServicePrincipal("states.amazonaws.com"),
            managed_policies=[
                _iam.ManagedPolicy.from_aws_managed_policy_name("AWSStepFunctionsFullAccess"),
                _iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
                _iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
            ],
            role_name="StateMachineExecutionRole",
         )
        
        definition = sfn.Chain.start(training_job_task) \
                              .next(create_model_task) \
                              .next(endpoint_config_task) \
                              .next(create_endpoint_task)
        
        state_machine = sfn.StateMachine(self, "mammpgraphy-state-machine",
            definition=definition,
            state_machine_name="mammpgraphy-state-machine",
            role=state_machine_role,
            timeout=Duration.minutes(60),
            removal_policy=RemovalPolicy.DESTROY    
        )

        startstate_lambda_role = _iam.Role(self, "StartStateLambdaRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="StartStateLambdaRole",
            path="/service-role/",
            managed_policies=[_iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                              _iam.ManagedPolicy.from_aws_managed_policy_name("AWSStepFunctionsFullAccess"),
                              _iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
                            ],
            inline_policies={
                "s3_access": _iam.PolicyDocument(statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:*"],
                        resources=["arn:aws:s3:::*/*"]
                    )
                ]),
            }
        )            
        
        startstate_lambda = lambda_.Function(self, "startstate-lambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="start-state.lambda_handler",
            code=lambda_.Code.from_asset("./mammo_scan_ecs/lambda/statestart"),
            role=startstate_lambda_role,
            function_name=f"start-state-{random_number}",
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "STATE_MACHINE_ARN": state_machine.state_machine_arn,
            }
        )


        
        
        
        



