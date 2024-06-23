import aws_cdk as core
import aws_cdk.assertions as assertions

from mammo_scan_ecs.mammo_scan_ecs_stack import MammoScanEcsStack

# example tests. To run these tests, uncomment this file along with the example
# resource in mammo_scan_ecs/mammo_scan_ecs_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MammoScanEcsStack(app, "mammo-scan-ecs")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
