import * as sns from 'aws-cdk-lib/aws-sns';
import { Construct } from 'constructs';

export interface CreateSnsTopicProps {
  prefix: string;
}

export function createSnsTopic(scope: Construct, props: CreateSnsTopicProps): sns.Topic {
  const { prefix } = props;

  const topic = new sns.Topic(scope, 'EventlyTopic', {
    topicName: `${prefix}-evently-notifications`,
    displayName: 'Evently Notifications',
  });

  return topic;
}
