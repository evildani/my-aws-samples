import json
import boto3
import os
import cfnresponse
import time
from datetime import datetime
from zscaler import ZscalerClient

# THis will be used to exit execution and report out of time when nuking
start_time = 0

def lambda_handler(event, context):
    start_time = time.time()
    """
    Main Lambda handler function that can be invoked directly or as a custom resource
    """
    print(f"Event received: {json.dumps(event)}")
    print(f"Environment: {os.environ.get('ENVIRONMENT')}")
    
    # Check if this is a CloudFormation custom resource event
    if 'RequestType' in event:
        return handle_cfn_event(event, context)
    else:
        return handle_direct_invocation(event, context)

def handle_cfn_event(event, context):
    """
    Handle CloudFormation custom resource events
    """
    try:
        request_type = event['RequestType']
        resource_properties = event.get('ResourceProperties', {})
        
        print(f"Processing CloudFormation {request_type} request")
        
        if request_type == 'Create':
            client_id = ""
            client_passwd = ""
            cloud = ""
            vanity = ""
            tenant_login = tenant_2_login(client_id, client_passwd, cloud, vanity)
            payload = nuke_tenant(tenant_login)
            result = process_cfn_create(event, resource_properties)
            result['PhysicalResourceId'] = context.log_stream_name
            cfnresponse.send(event, context, cfnresponse.SUCCESS, result)
        elif request_type == 'Update':
            result = process_cfn_update(event, resource_properties)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, result)
        elif request_type == 'Delete':
            result = process_cfn_delete(event, resource_properties)
            result['PhysicalResourceId'] = context.log_stream_name
            cfnresponse.send(event, context, cfnresponse.SUCCESS, result)
        else:
            cfnresponse.send(event, context, cfnresponse.FAILED, {
                'Error': f'Unknown request type: {request_type}'
            })
            
    except Exception as e:
        print(f"Error in handle_cfn_event: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {
            'Error': str(e)
        })

def handle_direct_invocation(event, context):
    """
    Handle direct Lambda invocations (not from CloudFormation)
    """
    try:
        # Get environment variables
        environment = os.environ.get('ENVIRONMENT', 'dev')
        
        # Process the event
        result = process_event(event, environment)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Lambda function executed successfully',
                'environment': environment,
                'timestamp': datetime.utcnow().isoformat(),
                'result': result
            })
        }
        
    except Exception as e:
        print(f"Error in handle_direct_invocation: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }

def process_cfn_create(event, resource_properties):
    """
    Process CloudFormation Create request
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    stack_name = event.get('StackId', '').split('/')[-1]
    
    # Create a deployment record
    deployment_data = {
        'stack_name': stack_name,
        'environment': environment,
        'deployment_time': datetime.utcnow().isoformat(),
        'resource_properties': resource_properties,
        'event_type': 'cloudformation_create'
    }
    return {
        'Message': 'CloudFormation stack creation processed successfully',
        'Environment': environment,
        'StackName': stack_name,
        'DeploymentTime': deployment_data['deployment_time'],
    }

def process_cfn_update(event, resource_properties):
    """
    Process CloudFormation Update request
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    stack_name = event.get('StackId', '').split('/')[-1]
    
    # Create an update record
    update_data = {
        'stack_name': stack_name,
        'environment': environment,
        'update_time': datetime.utcnow().isoformat(),
        'resource_properties': resource_properties,
        'event_type': 'cloudformation_update'
    }
    return {
        'Message': 'CloudFormation stack update processed successfully',
        'Environment': environment,
        'StackName': stack_name,
        'UpdateTime': update_data['update_time'],
    }

def process_cfn_delete(event, resource_properties):
    """
    Process CloudFormation Delete request
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    stack_name = event.get('StackId', '').split('/')[-1]
    
    # Create a deletion record
    deletion_data = {
        'stack_name': stack_name,
        'environment': environment,
        'deletion_time': datetime.utcnow().isoformat(),
        'resource_properties': resource_properties,
        'event_type': 'cloudformation_delete'
    }
    return {
        'Message': 'CloudFormation stack deletion processed successfully',
        'Environment': environment,
        'StackName': stack_name,
        'DeletionTime': deletion_data['deletion_time'],
    }

#return time in format: '2012-09-12 23:18:39'
def beutify_epoch(time):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time))

def process_event(event, environment):
    """
    Process regular Lambda invocation events
    """
    result = {
        'event_type': event.get('type', 'unknown'),
        'data_processed': False,
    }
    return result

def tenant_2_login(client_id, client_passwd, cloud, vanity):
    print(f"Login to Tenant")
    config = {
        "clientId": client_id,
        "clientSecret": client_passwd,
        "vanityDomain": vanity,
        "cloud": cloud, # (Optional)
    }
    with ZscalerClient(config) as client:
        users, _, err = client.zia.user_management.list_users()
        if err:
            print("Error:", err)
        else:
            print(users[0]["name"])  # Pythonic dict access
            return client

def nuke_tenant(event, login_obj ):
    print("Starting to Nuke tenant")
    user_category, response, error = login_obj.zia.url_categories.get_category('USER_DEFINED')
    print(f"Found Categories to delete: {len(user_category)}")
    for category in user_category:
        cat_id = category['id']
        login_obj.zia.url_categories.delete_category(category_id=cat_id)
    print(f"Finished Deleting Categories")
