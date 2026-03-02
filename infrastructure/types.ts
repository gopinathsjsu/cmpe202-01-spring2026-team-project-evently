import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sns from 'aws-cdk-lib/aws-sns';

export interface OutputsInput {
  bucket: s3.IBucket;
  vpc: ec2.IVpc;
  topic?: sns.ITopic;
}
