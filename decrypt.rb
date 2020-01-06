require 'aws-sdk-s3'

S3 = Aws::S3::Encryption::Client.new(kms_key_id: ENV['KMS'])

def handler(event:, context:)
  puts event
  begin
    object = S3.get_object(bucket: event['bucket'], key: event['key'])
  rescue Aws::S3::Errors::NoSuchKey => _e
    puts 'Not found'
    nil
  else
    object.body.string
  end
end
