# IAM Policies

This directory contains the IAM policies used by the **Cloud Cost Monitoring and Alert System**. The policies are separated by responsibility to make the permissions easier to review, maintain, and explain.

## Files

| File | Purpose |
|---|---|
| `cloud-cost-monitor-application-policy.json` | Allows the Lambda function to retrieve AWS cost data from Cost Explorer and publish cost reports or alerts to Amazon SNS. |
| `cloud-cost-dashboard-s3-upload.json` | Allows the Lambda function to upload the generated HTML dashboard to the designated Amazon S3 bucket. |
| `eventbridge-scheduler-invoke-lambda-policy.json` | Allows the EventBridge Scheduler execution role to invoke the cost-report Lambda function. |
| `eventbridge-scheduler-trust-policy.json` | Allows the EventBridge Scheduler service to assume its IAM execution role. |

## Permission Flow

1. EventBridge Scheduler assumes its execution role by using the trust policy.
2. The scheduler execution role invokes the Lambda function.
3. The Lambda execution role reads cost data from AWS Cost Explorer.
4. The Lambda function uploads the generated dashboard to Amazon S3.
5. The Lambda function publishes the weekly cost summary or alert to Amazon SNS.
6. Lambda execution logs are written to Amazon CloudWatch Logs through the AWS managed policy `AWSLambdaBasicExecutionRole`.

## Required Placeholders

The repository versions of these policies must not contain private AWS account information. Replace the following placeholders only when deploying the policies to your own AWS account:

| Placeholder | Replace with |
|---|---|
| `YOUR_ACCOUNT_ID` | Your 12-digit AWS account ID |
| `YOUR_BUCKET_NAME` | The S3 bucket used for the cost dashboard |
| `YOUR_LAMBDA_FUNCTION_NAME` | The Lambda function that generates the cost report |
| `YOUR_AWS_REGION` | The AWS Region containing the related resources, such as `us-east-1` |

Do not commit access keys, secret access keys, email addresses, or other credentials to this directory.

## Deployment Notes

- Attach `cloud-cost-monitor-application-policy.json` and `cloud-cost-dashboard-s3-upload.json` to the Lambda execution role.
- Attach the AWS managed policy `AWSLambdaBasicExecutionRole` to the same Lambda execution role for CloudWatch Logs access.
- Use `eventbridge-scheduler-trust-policy.json` as the trust relationship for the EventBridge Scheduler execution role.
- Attach `eventbridge-scheduler-invoke-lambda-policy.json` to the EventBridge Scheduler execution role.
- Confirm that the Region, account ID, bucket name, SNS topic ARN, and Lambda function ARN match the deployed resources.

## Security Design

The policies follow the principle of least privilege by separating Lambda application permissions, S3 upload access, scheduler invocation access, and the scheduler trust relationship. Resource-level permissions are used where AWS supports them.

AWS Cost Explorer actions such as `ce:GetCostAndUsage` require `"Resource": "*"`; this is an AWS service limitation and does not grant permission to modify billing data.

## Validation

Before deployment:

1. Validate the JSON syntax of every policy file.
2. Replace all required placeholders in the AWS Console version.
3. Review the policies with IAM Access Analyzer.
4. Test the Lambda function manually.
5. Confirm the dashboard upload, SNS notification, EventBridge invocation, and CloudWatch logs.

> The JSON files in this repository are portfolio-safe templates. The policies deployed in AWS must contain the actual resource ARNs.
