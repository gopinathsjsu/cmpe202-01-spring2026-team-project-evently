/**
 * VPC – Isolated network for Evently.
 *
 * Creates a VPC with:
 * - Public subnets (for ALB and NAT gateway)
 * - Private subnets (for API EC2 and database)
 * - One NAT gateway to allow private instances to reach the internet (updates, S3, etc.)
 */

import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export interface CreateVpcProps {
  prefix: string;
}

/**
 * Creates the Evently VPC with public and private subnets across 2 AZs.
 */
export function createVpc(scope: Construct, props: CreateVpcProps): ec2.Vpc {
  const { prefix } = props;

  return new ec2.Vpc(scope, 'Vpc', {
    vpcName: `${prefix}-vpc`,
    maxAzs: 2,
    natGateways: 1, // One NAT to reduce cost; increase for higher availability
    subnetConfiguration: [
      {
        name: 'Public',
        subnetType: ec2.SubnetType.PUBLIC,
        cidrMask: 24,
      },
      {
        name: 'Private',
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        cidrMask: 24,
      },
    ],
  });
}
