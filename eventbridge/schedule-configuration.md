# EventBridge Scheduler Configuration

This document records the Amazon EventBridge Scheduler configuration used to run the cloud cost report automatically every week.

## Schedule Settings

| Setting | Value |
| --- | --- |
| Schedule name | `weekly-cloud-cost-report` |
| Schedule group | `default` |
| Schedule type | Recurring schedule |
| Schedule expression | `cron(0 9 ? * MON *)` |
| Time zone | `Asia/Tokyo` |
| Flexible time window | Off |
| Schedule state | Enabled |
| Action after schedule completion | None |

The schedule runs every Monday at 09:00 Japan Standard Time (JST).

## Target Settings

| Setting | Value |
| --- | --- |
| Target service | AWS Lambda |
| Lambda function | `cloud-cost-report-generator` |
| Payload | `{}` |
| Execution role | EventBridge Scheduler execution role |

The execution role must allow only the following action on the target Lambda function:

```text
lambda:InvokeFunction
```

The related IAM policy examples are stored in:

- `../iam/eventbridge-scheduler-invoke-lambda-policy.json`
- `../iam/eventbridge-scheduler-trust-policy.json`

## Retry and Failure Settings

The AWS default retry settings may be used for this portfolio project. A dead-letter queue is optional. For a production environment, configure an Amazon SQS dead-letter queue and review the retry policy based on operational requirements.

## Console Setup

1. Open **Amazon EventBridge** in the AWS Management Console.
2. Select **Scheduler**, and then choose **Create schedule**.
3. Enter `weekly-cloud-cost-report` as the schedule name.
4. Select **Recurring schedule** and enter `cron(0 9 ? * MON *)`.
5. Set the time zone to `Asia/Tokyo`.
6. Turn **Flexible time window** off.
7. Select **AWS Lambda Invoke** as the target.
8. Choose the `cloud-cost-report-generator` function.
9. Use `{}` as the input payload.
10. Select or create an execution role that can invoke only this Lambda function.
11. Enable the schedule and create it.

## Verification

After the scheduled time, confirm the following:

- The Lambda function was invoked successfully.
- A new log stream appears in Amazon CloudWatch Logs.
- The S3 dashboard was updated.
- The SNS report email was received when email delivery is enabled.

## Security Notes

- Do not commit an AWS account ID or a full resource ARN containing an account ID.
- Limit `lambda:InvokeFunction` to the target Lambda function ARN.
- Keep the Scheduler trust policy limited to `scheduler.amazonaws.com`.

