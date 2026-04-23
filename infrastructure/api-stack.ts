import * as cdk from 'aws-cdk-lib';
import * as autoscaling from 'aws-cdk-lib/aws-autoscaling';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface ApiStackProps extends cdk.StackProps {
  projectName: string;
  environment: string;
  /**
   * VPC from another stack (e.g. tests). Omit when using `foundationVpcExportPrefix`.
   */
  vpc?: ec2.IVpc;
  /**
   * Import VPC + subnets from foundation stack CloudFormation exports
   * (`{prefix}-VpcId`, `{prefix}-VpcPublicSubnet1Id`, …). Same prefix as foundation `namePrefix`.
   */
  foundationVpcExportPrefix?: string;
  /**
   * Full ECR image URI, for example:
   * 123456789012.dkr.ecr.us-west-2.amazonaws.com/evently-backend:latest
   */
  apiImageUri: string;
  instanceType?: string;
  minCapacity?: number;
  desiredCapacity?: number;
  maxCapacity?: number;
  apiPort?: number;
  healthCheckPath?: string;
  /**
   * SSM parameter names that store backend environment values.
   * Example values in SSM Parameter Store:
   * - /evently/dev/DATABASE_URL
   * - /evently/dev/SESSION_SECRET_KEY
   */
  ssmParameterNames?: Record<string, string>;
}

export class EventlyApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const prefix = `${props.projectName}-${props.environment}`;
    const apiPort = props.apiPort ?? 8000;
    const healthCheckPath = props.healthCheckPath ?? '/health';

    let vpc: ec2.IVpc;
    if (props.foundationVpcExportPrefix) {
      const p = props.foundationVpcExportPrefix;
      const azs = cdk.Fn.getAzs(this.region);
      // Foundation VPC uses maxAzs: 2 — pass two explicit AZ tokens so subnet construct IDs stay unique.
      vpc = ec2.Vpc.fromVpcAttributes(this, 'ImportedVpc', {
        vpcId: cdk.Fn.importValue(`${p}-VpcId`),
        availabilityZones: [cdk.Fn.select(0, azs), cdk.Fn.select(1, azs)],
        publicSubnetIds: [
          cdk.Fn.importValue(`${p}-VpcPublicSubnet1Id`),
          cdk.Fn.importValue(`${p}-VpcPublicSubnet2Id`),
        ],
        privateSubnetIds: [
          cdk.Fn.importValue(`${p}-VpcPrivateSubnet1Id`),
          cdk.Fn.importValue(`${p}-VpcPrivateSubnet2Id`),
        ],
      });
    } else if (props.vpc) {
      vpc = props.vpc;
    } else {
      throw new Error(
        'EventlyApiStack requires either `vpc` or `foundationVpcExportPrefix` (foundation stack exports).'
      );
    }

    const albSg = new ec2.SecurityGroup(this, 'ApiAlbSg', {
      vpc,
      description: 'Security group for Evently API ALB',
      allowAllOutbound: true,
      securityGroupName: `${prefix}-api-alb-sg`,
    });
    albSg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'Allow HTTP');

    const apiSg = new ec2.SecurityGroup(this, 'ApiEc2Sg', {
      vpc,
      description: 'Security group for Evently API EC2 instances',
      allowAllOutbound: true,
      securityGroupName: `${prefix}-api-ec2-sg`,
    });
    apiSg.addIngressRule(albSg, ec2.Port.tcp(apiPort), 'Allow API traffic from ALB');

    const alb = new elbv2.ApplicationLoadBalancer(this, 'ApiAlb', {
      vpc,
      internetFacing: true,
      securityGroup: albSg,
      loadBalancerName: `${prefix}-api-alb`,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    const targetGroup = new elbv2.ApplicationTargetGroup(this, 'ApiTargetGroup', {
      vpc,
      protocol: elbv2.ApplicationProtocol.HTTP,
      port: apiPort,
      targetType: elbv2.TargetType.INSTANCE,
      healthCheck: {
        enabled: true,
        path: healthCheckPath,
        healthyHttpCodes: '200-399',
        interval: cdk.Duration.seconds(30),
      },
      targetGroupName: `${prefix}-api-tg`,
    });

    alb.addListener('HttpListener', {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      defaultTargetGroups: [targetGroup],
    });

    const role = new iam.Role(this, 'ApiEc2Role', {
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      description: 'Role for Evently API EC2 instances',
      roleName: `${prefix}-api-ec2-role`,
    });
    role.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore')
    );
    role.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchAgentServerPolicy')
    );
    role.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonEC2ContainerRegistryReadOnly')
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['ssm:GetParameter', 'ssm:GetParameters'],
        resources: [
          this.formatArn({
            service: 'ssm',
            region: this.region,
            account: this.account,
            resource: 'parameter',
            resourceName: `/${props.projectName}/${props.environment}/*`,
          }),
        ],
      })
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['kms:Decrypt'],
        resources: ['*'],
        conditions: {
          StringEquals: {
            'kms:ViaService': `ssm.${this.region}.amazonaws.com`,
          },
        },
      })
    );

    const machineImage = ec2.MachineImage.latestAmazonLinux2023();
    const userData = ec2.UserData.forLinux();
    const launchTemplate = new ec2.LaunchTemplate(this, 'ApiLaunchTemplate', {
      launchTemplateName: `${prefix}-api-lt`,
      machineImage,
      instanceType: new ec2.InstanceType(props.instanceType ?? 't3.micro'),
      role,
      securityGroup: apiSg,
      requireImdsv2: true,
      userData,
    });

    const envVarSources: Record<string, string> = {
      ...props.ssmParameterNames,
    };

    const defaultParameterPrefix = `/${props.projectName}/${props.environment}`;
    const defaults: Record<string, string> = {
      DATABASE_URL: `${defaultParameterPrefix}/DATABASE_URL`,
      SESSION_SECRET_KEY: `${defaultParameterPrefix}/SESSION_SECRET_KEY`,
      FRONTEND_URL: `${defaultParameterPrefix}/FRONTEND_URL`,
      OAUTH_CLIENT_ID: `${defaultParameterPrefix}/OAUTH_CLIENT_ID`,
      OAUTH_CLIENT_SECRET: `${defaultParameterPrefix}/OAUTH_CLIENT_SECRET`,
      ADMIN_EMAILS: `${defaultParameterPrefix}/ADMIN_EMAILS`,
    };
    for (const [key, value] of Object.entries(defaults)) {
      if (!envVarSources[key]) {
        envVarSources[key] = value;
      }
    }

    userData.addCommands(
      'set -euxo pipefail',
      'dnf update -y',
      'dnf install -y docker jq',
      'systemctl enable docker',
      'systemctl start docker',
      'usermod -aG docker ec2-user || true',
      `aws ecr get-login-password --region ${this.region} | docker login --username AWS --password-stdin ${props.apiImageUri.split('/')[0]}`,
      `docker pull ${props.apiImageUri}`,
      'mkdir -p /opt/evently',
      ': > /opt/evently/backend.env'
    );

    for (const [envName, parameterName] of Object.entries(envVarSources)) {
      userData.addCommands(
        `${envName}=""`,
        `for i in $(seq 1 12); do ${envName}=$(aws ssm get-parameter --name "${parameterName}" --with-decryption --query Parameter.Value --output text --region ${this.region} 2>/tmp/${envName}.err) && break; echo "Retrying SSM read for ${envName} ($i/12)"; sleep 5; done`,
        `if [ -z "$${envName}" ]; then echo "Failed to resolve ${envName} from ${parameterName}"; cat /tmp/${envName}.err || true; exit 1; fi`,
        `printf '%s=%s\\n' "${envName}" "$${envName}" >> /opt/evently/backend.env`
      );
    }

    userData.addCommands(
      'docker rm -f evently-api || true',
      `docker run -d --name evently-api --restart unless-stopped -p ${apiPort}:${apiPort} --env-file /opt/evently/backend.env ${props.apiImageUri}`
    );

    const asg = new autoscaling.AutoScalingGroup(this, 'ApiAsg', {
      vpc,
      launchTemplate,
      minCapacity: props.minCapacity ?? 2,
      desiredCapacity: props.desiredCapacity ?? 2,
      maxCapacity: props.maxCapacity ?? 4,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      autoScalingGroupName: `${prefix}-api-asg`,
      healthCheck: autoscaling.HealthCheck.elb({ grace: cdk.Duration.minutes(3) }),
    });

    asg.attachToApplicationTargetGroup(targetGroup);
    asg.scaleOnCpuUtilization('ApiCpuScaling', {
      targetUtilizationPercent: 60,
      cooldown: cdk.Duration.seconds(180),
    });

    new cdk.CfnOutput(this, 'ApiAlbDnsName', {
      description: 'Public DNS for Evently API load balancer',
      value: alb.loadBalancerDnsName,
      exportName: `${prefix}-ApiAlbDnsName`,
    });
    new cdk.CfnOutput(this, 'ApiAsgName', {
      description: 'Auto Scaling Group name for Evently API',
      value: asg.autoScalingGroupName,
      exportName: `${prefix}-ApiAsgName`,
    });
  }
}
