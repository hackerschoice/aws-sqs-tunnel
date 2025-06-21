import boto3

# Create SQS client
sqs = boto3.client('sqs', region_name='ap-south-1')

queue_url = 'https://sqs.ap-south-1.amazonaws.com/278902205627/my-queue'
print(f'The queue URL is: {queue_url}')
sqs.delete_queue(QueueUrl=queue_url)

print('Queue deleted successfully')