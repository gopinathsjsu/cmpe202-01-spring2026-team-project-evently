import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { OutputsInput } from './types';

export interface CreateOutputsProps extends OutputsInput {
  prefix: string;
}

export function createOutputs(scope: Construct, props: CreateOutputsProps): void {
  const { prefix, bucket, vpc, topic } = props;

  new cdk.CfnOutput(scope, 'S3AssetsBucket', {
    description: 'S3 bucket for event assets and uploads',
    value: bucket.bucketName,
    exportName: `${prefix}-S3AssetsBucket`,
  });

  new cdk.CfnOutput(scope, 'VpcId', {
    description: 'VPC ID',
    value: vpc.vpcId,
    exportName: `${prefix}-VpcId`,
  });

  if (topic) {
    new cdk.CfnOutput(scope, 'SnsTopicArn', {
      description: 'SNS topic ARN for notifications',
      value: topic.topicArn,
      exportName: `${prefix}-SnsTopicArn`,
    });
  }
}
