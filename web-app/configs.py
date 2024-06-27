import boto3

region_name = boto3.Session().region_name


def get_parameter(name):
    """
    This function retrieves a specific value from Systems Manager"s ParameterStore.
    """     
    ssm_client = boto3.client("ssm",region_name=region_name)
    response = ssm_client.get_parameter(Name=name)
    value = response["Parameter"]["Value"]
    
    return value