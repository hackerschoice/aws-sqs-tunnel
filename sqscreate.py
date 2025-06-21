import boto3

# Create SQS client
sqs = boto3.client('sqs', region_name='ap-south-1')

print('Creating Queues...')
# Create a queue
queue_attributes = {'DelaySeconds': '0',
        'MessageRetentionPeriod': '60'}
response = sqs.create_queue(QueueName='Tx-SQS', Attributes=queue_attributes)
queue_url = response['QueueUrl']
print(f'Tx URL: {queue_url}')
response = sqs.create_queue(QueueName='Rx-SQS', Attributes=queue_attributes)
queue_url = response['QueueUrl']
print(f'Tx URL: {queue_url}')

print('Substitute these queue URLs in awsproxy.py')

# sqs.delete_queue(QueueUrl=queue_url)
