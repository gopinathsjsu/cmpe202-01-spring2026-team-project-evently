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

  new cdk.CfnOutput(scope, 'VpcCidr', {
    description: 'VPC IPv4 CIDR (for security group rules in sibling stacks)',
    value: vpc.vpcCidrBlock,
    exportName: `${prefix}-VpcCidr`,
  });

  new cdk.CfnOutput(scope, 'VpcPublicSubnet1Id', {
    description: 'VPC public subnet 1 ID',
    value: vpc.publicSubnets[0].subnetId,
    exportName: `${prefix}-VpcPublicSubnet1Id`,
  });

  new cdk.CfnOutput(scope, 'VpcPublicSubnet2Id', {
    description: 'VPC public subnet 2 ID',
    value: vpc.publicSubnets[1].subnetId,
    exportName: `${prefix}-VpcPublicSubnet2Id`,
  });

  new cdk.CfnOutput(scope, 'VpcPrivateSubnet1Id', {
    description: 'VPC private subnet 1 ID',
    value: vpc.privateSubnets[0].subnetId,
    exportName: `${prefix}-VpcPrivateSubnet1Id`,
  });

  new cdk.CfnOutput(scope, 'VpcPrivateSubnet2Id', {
    description: 'VPC private subnet 2 ID',
    value: vpc.privateSubnets[1].subnetId,
    exportName: `${prefix}-VpcPrivateSubnet2Id`,
  });

  if (topic) {
    new cdk.CfnOutput(scope, 'SnsTopicArn', {
      description: 'SNS topic ARN for notifications',
      value: topic.topicArn,
      exportName: `${prefix}-SnsTopicArn`,
    });
  }
}
