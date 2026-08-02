# Lambda 関数

[English](README.md)

## 概要

`lambda_function.py` は、AWS Cloud Cost Monitoring System のメインコードです。AWS Cost Explorer からコストデータを取得します。そして、2つの7日間の料金を比較します。その後、HTML ダッシュボードを作り、Amazon S3 にアップロードします。設定が有効な場合は、Amazon SNS で毎週のメールレポートも送ります。

## 処理の流れ

Lambda 関数は、次の順番で処理します。

1. 日本時間（JST）で必要な日付を計算します。
2. AWS サービスごとの料金を Cost Explorer から取得します。
3. 最近の完了した7日間と、その前の7日間を比較します。
4. 今月1日から昨日までの料金を取得します。
5. 料金が増えたサービスを見つけます。
6. HTML ダッシュボードを作ります。
7. ダッシュボードを S3 バケットにアップロードします。
8. メール設定が有効な場合、SNS でレポートを送ります。

> Cost Explorer の終了日は、データに入りません。そのため、この関数は今日を終了日にして、昨日までの料金を表示します。

## Lambda の設定

おすすめの設定は次のとおりです。

| 項目 | 値 |
| --- | --- |
| ランタイム | Python 3.x |
| ハンドラー | `lambda_function.lambda_handler` |
| アーキテクチャ | `arm64` |
| リージョン | `us-east-1` |
| タイムアウト | 30 秒 |

## 環境変数

| 変数 | 必須 | デフォルト | 説明 |
| --- | --- | --- | --- |
| `S3_BUCKET_NAME` | はい | なし | ダッシュボードを保存する S3 バケット |
| `SNS_TOPIC_ARN` | メール送信で必要 | なし | 毎週のレポートを送る SNS Topic |
| `DASHBOARD_OBJECT_KEY` | いいえ | `index.html` | S3 に保存するファイル名 |
| `SEND_WEEKLY_EMAIL` | いいえ | `true` | `false` にするとメールを送りません |

`AWS_REGION` は Lambda が自動で設定します。値がない場合、コードは `us-east-1` を使います。

本当の AWS アカウント ID、メールアドレス、秘密の情報を公開 GitHub に保存しないでください。

## 必要な IAM 権限

Lambda の実行ロールには、次の権限が必要です。

- コストデータを読むための `ce:GetCostAndUsage`
- ダッシュボードを保存するための `s3:PutObject`
- メールを送る場合は `sns:Publish`
- CloudWatch Logs の権限。通常は `AWSLambdaBasicExecutionRole` を使います。

IAM Policy の例は、リポジトリの `iam/` フォルダーにあります。S3 と SNS の権限は、できるだけこのプロジェクトのリソースだけに設定します。

## ライブラリ

この関数は Python の標準ライブラリと `boto3` を使います。`boto3` は AWS Lambda の Python ランタイムに入っています。そのため、外部パッケージや Lambda Layer は必要ありません。

## 手動テスト

特別な Event データは必要ありません。Lambda Console で、次の Test Event を使います。

```json
{}
```

実行が成功すると、`200` のステータスコードと JSON データを返します。JSON には、S3 バケット名、ダッシュボードのファイル名、料金、メール設定、料金が増えたサービスの数、作成時刻が入ります。

戻り値の例:

```json
{
  "statusCode": 200,
  "body": "{\"message\": \"AWS cost report generated successfully.\", ...}"
}
```

テストの後、次の項目を確認します。

- Lambda の結果に `statusCode: 200` があります。
- S3 にダッシュボードのファイルがあります。
- ダッシュボードに最近の7日間、前の7日間、今月の料金が表示されます。
- CloudWatch Logs に成功のメッセージがあります。
- `SEND_WEEKLY_EMAIL=true` で `SNS_TOPIC_ARN` がある場合、SNS のメールが届きます。

## 自動実行

Amazon EventBridge Scheduler を使うと、この関数を自動で実行できます。このプロジェクトでは、`Asia/Tokyo` のタイムゾーンで毎週実行します。例えば、次の式は毎週月曜日の午前9時に実行します。

```text
cron(0 9 ? * MON *)
```

## エラーについて

エラーが発生した場合、詳しい情報を CloudWatch Logs に記録します。その後、エラーをもう一度送ります。そのため、Lambda の実行結果は「失敗」になり、問題を確認できます。

よくある原因:

- `S3_BUCKET_NAME` が設定されていない
- S3 バケット名や権限が正しくない
- Cost Explorer の権限がない
- SNS Topic ARN や `sns:Publish` 権限が正しくない
- AWS アカウントで Cost Explorer がまだ有効になっていない

