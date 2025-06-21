import boto3
import json

# Create SQS client
sqs = boto3.client('sqs', region_name='ap-south-1')

queue_url = 'https://sqs.ap-south-1.amazonaws.com/278902205627/my-queue'

message = {'Body': 'Hello from Amazon SQS!'}
response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message))
print(response)

print("posted")