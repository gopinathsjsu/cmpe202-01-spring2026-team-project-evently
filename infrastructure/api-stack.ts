import * as cdk from 'aws-cdk-lib';
import * as autoscaling from 'aws-cdk-lib/aws-autoscaling';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elasticache from 'aws-cdk-lib/aws-elasticache';
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
  enableNotificationWorker?: boolean;
  valkeyNodeType?: string;
  /**
   * SSM parameter names that store backend environment values.
   * Example values in SSM Parameter Store:
   * - /evently/dev/DATABASE_URL
   * - /evently/dev/SESSION_SECRET_KEY
   */
  ssmParameterNames?: Record<string, string>;
  /**
   * SSM parameter names that should be loaded when present, but should not
   * fail instance boot when missing.
   */
  optionalSsmParameterNames?: Record<string, string>;
}

export class EventlyApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const prefix = `${props.projectName}-${props.environment}`;
    const apiPort = props.apiPort ?? 8000;
    const healthCheckPath = props.healthCheckPath ?? '/health';
    const enableNotificationWorker = props.enableNotificationWorker ?? true;
    const minCapacity = props.minCapacity ?? 2;
    const desiredCapacity = props.desiredCapacity ?? 2;
    const maxCapacity = props.maxCapacity ?? 4;

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

    let valkeyReplicationGroup: elasticache.CfnReplicationGroup | undefined;
    if (enableNotificationWorker) {
      const valkeyPort = 6379;
      const valkeySg = new ec2.SecurityGroup(this, 'ValkeySg', {
        vpc,
        description: 'Security group for Evently Valkey',
        allowAllOutbound: true,
        securityGroupName: `${prefix}-valkey-sg`,
      });
      valkeySg.addIngressRule(
        apiSg,
        ec2.Port.tcp(valkeyPort),
        'Allow Redis-compatible queue traffic from API EC2 instances'
      );

      const valkeySubnetGroup = new elasticache.CfnSubnetGroup(this, 'ValkeySubnetGroup', {
        cacheSubnetGroupName: `${prefix}-valkey-subnets`,
        description: 'Private subnets for Evently Valkey',
        subnetIds: vpc.privateSubnets.map((subnet) => subnet.subnetId),
      });

      valkeyReplicationGroup = new elasticache.CfnReplicationGroup(
        this,
        'ValkeyReplicationGroup',
        {
          replicationGroupId: `${prefix}-valkey`,
          replicationGroupDescription: 'Evently Redis-compatible queue for Arq jobs',
          engine: 'valkey',
          cacheNodeType: props.valkeyNodeType ?? 'cache.t4g.micro',
          numCacheClusters: 1,
          automaticFailoverEnabled: false,
          multiAzEnabled: false,
          transitEncryptionEnabled: false,
          port: valkeyPort,
          cacheSubnetGroupName: valkeySubnetGroup.ref,
          securityGroupIds: [valkeySg.securityGroupId],
          autoMinorVersionUpgrade: true,
        }
      );
      valkeyReplicationGroup.addDependency(valkeySubnetGroup);
    }

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
        // Instances bootstrap Docker + image pull on first boot; keep checks frequent
        // so they become healthy quickly once the app starts.
        interval: cdk.Duration.seconds(15),
        timeout: cdk.Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
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
    const optionalEnvVarSources: Record<string, string> = {
      ...props.optionalSsmParameterNames,
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
    const optionalDefaults: Record<string, string> = {
      RESEND_API_KEY: `${defaultParameterPrefix}/RESEND_API_KEY`,
      EMAIL_FROM: `${defaultParameterPrefix}/EMAIL_FROM`,
    };
    for (const [key, value] of Object.entries(optionalDefaults)) {
      if (!optionalEnvVarSources[key]) {
        optionalEnvVarSources[key] = value;
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

    for (const [envName, parameterName] of Object.entries(optionalEnvVarSources)) {
      userData.addCommands(
        `if ${envName}=$(aws ssm get-parameter --name "${parameterName}" --with-decryption --query Parameter.Value --output text --region ${this.region} 2>/tmp/${envName}.err); then printf '%s=%s\\n' "${envName}" "$${envName}" >> /opt/evently/backend.env; else echo "Optional SSM parameter ${parameterName} not found; ${envName} will be unset"; cat /tmp/${envName}.err || true; fi`
      );
    }

    if (valkeyReplicationGroup) {
      userData.addCommands(
        `printf '%s=%s\\n' "REDIS_URL" "redis://${valkeyReplicationGroup.attrPrimaryEndPointAddress}:${valkeyReplicationGroup.attrPrimaryEndPointPort}/0" >> /opt/evently/backend.env`
      );
    }

    userData.addCommands(
      'docker rm -f evently-worker || true',
      'docker rm -f evently-api || true',
      `docker run -d --name evently-api --restart unless-stopped -p ${apiPort}:${apiPort} --env-file /opt/evently/backend.env ${props.apiImageUri}`
    );
    if (enableNotificationWorker) {
      userData.addCommands(
        `docker run -d --name evently-worker --restart unless-stopped --env-file /opt/evently/backend.env ${props.apiImageUri} uv run notif-worker`
      );
    }

    const asg = new autoscaling.AutoScalingGroup(this, 'ApiAsg', {
      vpc,
      launchTemplate,
      minCapacity,
      desiredCapacity,
      maxCapacity,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      autoScalingGroupName: `${prefix}-api-asg`,
      // Give user-data + container startup enough time before ELB health verdicts.
      healthCheck: autoscaling.HealthCheck.elb({ grace: cdk.Duration.minutes(8) }),
      updatePolicy: autoscaling.UpdatePolicy.rollingUpdate({
        maxBatchSize: 1,
        minInstancesInService: Math.max(0, Math.min(desiredCapacity - 1, minCapacity)),
        waitOnResourceSignals: false,
        pauseTime: cdk.Duration.minutes(8),
      }),
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
    if (valkeyReplicationGroup) {
      new cdk.CfnOutput(this, 'ValkeyEndpoint', {
        description: 'Private Valkey endpoint for Evently background jobs',
        value: valkeyReplicationGroup.attrPrimaryEndPointAddress,
        exportName: `${prefix}-ValkeyEndpoint`,
      });
      new cdk.CfnOutput(this, 'ValkeyPort', {
        description: 'Valkey port for Evently background jobs',
        value: valkeyReplicationGroup.attrPrimaryEndPointPort,
        exportName: `${prefix}-ValkeyPort`,
      });
    }
  }
}
