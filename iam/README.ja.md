# IAM ポリシー

このディレクトリには、**Cloud Cost Monitoring and Alert System** で使用する IAM ポリシーが含まれています。権限を確認・保守・説明しやすくするため、役割ごとにポリシーを分離しています。

## ファイル一覧

| ファイル | 目的 |
|---|---|
| `cloud-cost-monitor-application-policy.json` | Lambda 関数が AWS Cost Explorer からコストデータを取得し、Amazon SNS にコストレポートまたはアラートを発行するための権限を定義します。 |
| `cloud-cost-dashboard-s3-upload.json` | Lambda 関数が生成した HTML ダッシュボードを、指定された Amazon S3 バケットへアップロードするための権限を定義します。 |
| `eventbridge-scheduler-invoke-lambda-policy.json` | EventBridge Scheduler の実行ロールが、コストレポート用 Lambda 関数を呼び出すための権限を定義します。 |
| `eventbridge-scheduler-trust-policy.json` | EventBridge Scheduler サービスが、その IAM 実行ロールを引き受けるための信頼ポリシーです。 |

## 権限の流れ

1. EventBridge Scheduler が信頼ポリシーを使用して実行ロールを引き受けます。
2. Scheduler の実行ロールが Lambda 関数を呼び出します。
3. Lambda の実行ロールが AWS Cost Explorer からコストデータを取得します。
4. Lambda 関数が生成したダッシュボードを Amazon S3 にアップロードします。
5. Lambda 関数が週次コストレポートまたはアラートを Amazon SNS に発行します。
6. AWS 管理ポリシー `AWSLambdaBasicExecutionRole` により、Lambda の実行ログが Amazon CloudWatch Logs に出力されます。

## 必要なプレースホルダー

リポジトリ内のポリシーには、AWS アカウントの機密情報を含めないでください。実際の AWS アカウントへデプロイするときのみ、以下のプレースホルダーを置き換えます。

| プレースホルダー | 置き換える値 |
|---|---|
| `YOUR_ACCOUNT_ID` | 12 桁の AWS アカウント ID |
| `YOUR_BUCKET_NAME` | コストダッシュボードを保存する S3 バケット名 |
| `YOUR_LAMBDA_FUNCTION_NAME` | コストレポートを生成する Lambda 関数名 |
| `YOUR_AWS_REGION` | 関連リソースが存在する AWS リージョン（例：`us-east-1`） |

アクセスキー、シークレットアクセスキー、メールアドレス、その他の認証情報をこのディレクトリへコミットしないでください。

## デプロイ時の注意事項

- `cloud-cost-monitor-application-policy.json` と `cloud-cost-dashboard-s3-upload.json` を Lambda 実行ロールにアタッチします。
- CloudWatch Logs への出力用として、AWS 管理ポリシー `AWSLambdaBasicExecutionRole` も同じ Lambda 実行ロールにアタッチします。
- `eventbridge-scheduler-trust-policy.json` を EventBridge Scheduler 実行ロールの信頼関係として設定します。
- `eventbridge-scheduler-invoke-lambda-policy.json` を EventBridge Scheduler 実行ロールにアタッチします。
- リージョン、アカウント ID、S3 バケット名、SNS トピック ARN、Lambda 関数 ARN が、実際にデプロイしたリソースと一致していることを確認します。

## セキュリティ設計

Lambda のアプリケーション権限、S3 へのアップロード権限、Scheduler の呼び出し権限、Scheduler の信頼関係を分離し、最小権限の原則を意識した構成にしています。AWS が対応している権限については、リソースレベルの制限を使用します。

`ce:GetCostAndUsage` などの AWS Cost Explorer アクションでは `"Resource": "*"` が必要です。これは AWS サービス側の仕様であり、請求データを変更する権限を付与するものではありません。

## 検証手順

デプロイ前に、以下を確認します。

1. すべてのポリシーファイルの JSON 構文を検証します。
2. AWS Console で使用するポリシー内の必須プレースホルダーを置き換えます。
3. IAM Access Analyzer でポリシーを確認します。
4. Lambda 関数を手動でテストします。
5. ダッシュボードのアップロード、SNS 通知、EventBridge からの呼び出し、CloudWatch Logs の出力を確認します。

> このリポジトリ内の JSON ファイルは、ポートフォリオ公開用の安全なテンプレートです。AWS にデプロイするポリシーには、実際のリソース ARN を設定してください。
