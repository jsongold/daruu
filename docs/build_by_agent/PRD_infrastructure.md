# PRD: Infrastructure（インフラストラクチャ）

## 目的
Daru PDFシステムを複数の環境（Docker Compose、GCP、AWS）に独立してデプロイできるようにする。各環境は独立した設定とデプロイメントパイプラインを持ち、相互に依存しない。

## 前提
- モノレポ構成（`apps/api`, `apps/orchestrator`, `apps/web`, `apps/contracts`）
- Clean Architectureに基づくサービス分離
- 各サービスは独立してスケール可能
- 永続化はSupabase（Postgres + Storage + Auth）を利用
- 非同期処理はCelery（または代替キュー）を使用

## 非目的（Non-Goals）
- 単一の統合デプロイメント（各環境は独立）
- インフラの自動スケーリング（初期MVPでは手動設定）
- マルチリージョン展開（各環境は単一リージョン想定）

## スコープ
- Docker Compose環境（ローカル開発・小規模運用）
- GCP環境（Cloud Run、Cloud Storage、Cloud SQL等）
- AWS環境（ECS/Fargate、S3、RDS等）
- 各環境の設定ファイル、デプロイスクリプト、ドキュメント

## 非スコープ
- CI/CDパイプラインの詳細実装（各環境のデプロイ方法のみ）
- モニタリング・ロギングの詳細設定（基本構成のみ）
- セキュリティポリシーの詳細（基本認証・ネットワーク設定のみ）

## アーキテクチャ原則

### サービス独立性
各サービス（API、Orchestrator、Web）は独立してデプロイ可能で、以下の原則に従う：
- **環境変数による設定**: 設定は環境変数で注入（12-factor原則）
- **サービスディスカバリー**: サービス間通信はURL/エンドポイントで解決
- **ステートレス**: サービスはステートレス（状態はSupabase/Redis等に保存）
- **ヘルスチェック**: 各サービスは`/health`エンドポイントを提供

### 依存関係
```
┌─────────────┐
│   Web UI    │ (Frontend)
└──────┬──────┘
       │ HTTP
┌──────▼──────┐
│  API Gateway│ (FastAPI)
└──────┬──────┘
       │ HTTP/Contract
┌──────▼──────────────┐
│   Orchestrator      │ (Pipeline Control)
└──────┬──────────────┘
       │ HTTP/Contract
┌──────▼────────────────────────┐
│  Services (Ingest/Extract/etc) │
└────────────────────────────────┘
       │
┌──────▼──────┐     ┌──────────┐
│   Supabase  │     │  Redis   │
│ (DB/Storage)│     │  (Queue) │
└─────────────┘     └──────────┘
```

## 環境別構成

### 1. Docker Compose環境

#### 目的
- ローカル開発環境
- 小規模運用・検証環境
- 全サービスを単一マシンで実行

#### 構成
```yaml
services:
  - api: FastAPI (Port 8000)
  - orchestrator: Orchestrator Service (Port 8001, optional)
  - web: Vite dev server (Port 5173) or Nginx (Port 80)
  - redis: Redis for Celery queue
  - celery-worker: Celery worker for async tasks
  - celery-beat: Celery beat for scheduled tasks (optional)
```

#### 特徴
- 全サービスを同一ネットワークで実行
- ボリュームマウントでコード変更を即時反映
- 環境変数は`.env`ファイルで管理
- Supabaseは外部サービスとして接続（ローカルPostgresも可）

#### ファイル構成
```
infra/docker-compose/
├── docker-compose.yml          # メイン設定
├── docker-compose.override.yml # 開発用オーバーライド（任意）
├── .env.example                # 環境変数テンプレート
├── nginx/
│   └── nginx.conf             # Web UI用リバースプロキシ（本番モード）
└── README.md                  # セットアップ手順
```

#### デプロイ方法
```bash
cd infra/docker-compose
cp .env.example .env
# .envを編集
docker-compose up -d
```

#### 受け入れ基準
- `docker-compose up`で全サービスが起動
- 各サービスの`/health`エンドポイントが応答
- Web UIからAPI経由でジョブ作成・実行が可能

---

### 2. GCP環境

#### 目的
- 本番環境（中規模〜大規模）
- Google Cloud Platformのマネージドサービス活用
- 自動スケーリング対応

#### 構成
```
┌─────────────────────────────────────────┐
│         Cloud Load Balancer             │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐         ┌──────▼────┐
│ Cloud  │         │  Cloud    │
│ Run    │         │  Run      │
│ (API)  │         │  (Web UI) │
└───┬────┘         └───────────┘
    │
    │ HTTP/Contract
┌───▼──────────────────────┐
│   Cloud Run              │
│   (Orchestrator)         │
└───┬──────────────────────┘
    │
┌───▼──────────────────────────────┐
│   Cloud Run (Services)            │
│   - Ingest Service                │
│   - Extract Service               │
│   - Fill Service                  │
│   - etc.                          │
└───┬──────────────────────────────┘
    │
┌───▼──────────┐    ┌──────────────┐
│  Cloud SQL   │    │  Cloud       │
│  (Postgres)  │    │  Storage     │
│  or Supabase │    │  (Artifacts) │
└──────────────┘    └──────────────┘
         │
┌────────▼──────────┐
│  Cloud Memorystore │
│  (Redis)           │
└────────────────────┘
```

#### サービス詳細

**Cloud Run（API）**
- FastAPIアプリケーション
- 最小インスタンス: 0（コールドスタート許容）または1（低レイテンシ）
- 最大インスタンス: 10（初期）
- CPU: 2 vCPU
- メモリ: 4 GiB
- タイムアウト: 300秒

**Cloud Run（Orchestrator）**
- オーケストレーションサービス
- 最小インスタンス: 0
- 最大インスタンス: 5
- CPU: 1 vCPU
- メモリ: 2 GiB

**Cloud Run（Services）**
- 各パイプラインサービス（Ingest/Extract/Fill等）
- 最小インスタンス: 0
- 最大インスタンス: 10（サービスごと）
- CPU: 1-2 vCPU（サービス依存）
- メモリ: 2-4 GiB（サービス依存）

**Cloud Run（Web UI）**
- 静的ファイル配信（Nginx）またはViteビルド成果物
- 最小インスタンス: 1
- 最大インスタンス: 3

**Cloud Memorystore（Redis）**
- Celeryブローカー・結果バックエンド
- インスタンスサイズ: basic（1GB）〜standard（10GB）

**Cloud Storage**
- PDF原本、プレビュー画像、OCR切り出し、生成物PDF
- バケット: `daru-pdf-documents`, `daru-pdf-previews`, `daru-pdf-crops`, `daru-pdf-outputs`
- ライフサイクルポリシー: 30日後にアーカイブ、90日後に削除（設定可能）

**Cloud SQL（オプション）**
- Supabaseの代替として使用する場合
- インスタンスタイプ: db-f1-micro（開発）〜db-n1-standard-2（本番）

#### ファイル構成
```
infra/gcp/
├── cloud-run/
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── cloudbuild.yaml
│   │   └── service.yaml          # Cloud Runサービス定義
│   ├── orchestrator/
│   │   ├── Dockerfile
│   │   ├── cloudbuild.yaml
│   │   └── service.yaml
│   ├── web/
│   │   ├── Dockerfile
│   │   ├── cloudbuild.yaml
│   │   └── service.yaml
│   └── services/                 # 各パイプラインサービス
│       ├── ingest/
│       ├── extract/
│       └── ...
├── terraform/                    # Infrastructure as Code（推奨）
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── cloud-run/
│       ├── memorystore/
│       └── storage/
├── scripts/
│   ├── deploy.sh                 # デプロイスクリプト
│   ├── setup.sh                  # 初期セットアップ
│   └── migrate.sh                # データベースマイグレーション
├── .env.gcp.example              # 環境変数テンプレート
└── README.md                     # セットアップ・デプロイ手順
```

#### デプロイ方法

**Terraform使用（推奨）**
```bash
cd infra/gcp/terraform
terraform init
terraform plan
terraform apply
```

**gcloud CLI使用**
```bash
cd infra/gcp/cloud-run/api
gcloud builds submit --tag gcr.io/PROJECT_ID/daru-api
gcloud run deploy daru-api --image gcr.io/PROJECT_ID/daru-api
```

**スクリプト使用**
```bash
cd infra/gcp/scripts
./setup.sh                    # 初回セットアップ（リソース作成）
./deploy.sh api               # APIデプロイ
./deploy.sh orchestrator      # Orchestratorデプロイ
./deploy.sh all               # 全サービスデプロイ
```

#### 環境変数（GCP固有）
```bash
# Cloud Run環境変数
GCP_PROJECT_ID=your-project-id
GCP_REGION=asia-northeast1
GCP_SERVICE_ACCOUNT=service-account@project.iam.gserviceaccount.com

# Cloud Storage
GCP_STORAGE_BUCKET_DOCUMENTS=daru-pdf-documents
GCP_STORAGE_BUCKET_PREVIEWS=daru-pdf-previews
GCP_STORAGE_BUCKET_CROPS=daru-pdf-crops
GCP_STORAGE_BUCKET_OUTPUTS=daru-pdf-outputs

# Cloud Memorystore (Redis)
GCP_REDIS_HOST=10.x.x.x
GCP_REDIS_PORT=6379

# Supabase（継続利用の場合）
DARU_SUPABASE_URL=https://xxx.supabase.co
DARU_SUPABASE_SERVICE_KEY=xxx
```

#### 受け入れ基準
- Terraform/スクリプトで全リソースが作成される
- 各Cloud Runサービスが正常に起動
- ロードバランサー経由でWeb UIとAPIにアクセス可能
- ジョブ作成・実行が正常に動作
- Cloud Storageへのファイルアップロード・取得が可能

---

### 3. AWS環境

#### 目的
- 本番環境（中規模〜大規模）
- AWSマネージドサービス活用
- 自動スケーリング対応

#### 構成
```
┌─────────────────────────────────────────┐
│      Application Load Balancer (ALB)    │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐         ┌──────▼────┐
│  ECS   │         │  S3 +     │
│ Fargate│         │ CloudFront│
│ (API)  │         │  (Web UI) │
└───┬────┘         └───────────┘
    │
    │ HTTP/Contract
┌───▼──────────────────────┐
│   ECS Fargate            │
│   (Orchestrator)         │
└───┬──────────────────────┘
    │
┌───▼──────────────────────────────┐
│   ECS Fargate (Services)          │
│   - Ingest Service                │
│   - Extract Service               │
│   - Fill Service                  │
│   - etc.                          │
└───┬──────────────────────────────┘
    │
┌───▼──────────┐    ┌──────────────┐
│  RDS          │    │  S3         │
│  (Postgres)   │    │  (Artifacts)│
│  or Supabase  │    └──────────────┘
└───────────────┘
         │
┌────────▼──────────┐
│  ElastiCache      │
│  (Redis)          │
└───────────────────┘
```

#### サービス詳細

**ECS Fargate（API）**
- タスク定義: `daru-api`
- CPU: 2 vCPU
- メモリ: 4 GiB
- デプロイ数: 最小1、最大10
- ターゲットグループ: ALBに接続

**ECS Fargate（Orchestrator）**
- タスク定義: `daru-orchestrator`
- CPU: 1 vCPU
- メモリ: 2 GiB
- デプロイ数: 最小0、最大5

**ECS Fargate（Services）**
- 各パイプラインサービス用タスク定義
- CPU: 1-2 vCPU（サービス依存）
- メモリ: 2-4 GiB（サービス依存）
- デプロイ数: 最小0、最大10（サービスごと）

**S3 + CloudFront（Web UI）**
- S3バケット: 静的ファイルホスティング
- CloudFront: CDN配信、カスタムドメイン対応

**ElastiCache（Redis）**
- ノードタイプ: cache.t3.micro（開発）〜cache.t3.medium（本番）
- クラスターモード: 無効（シンプルモード）

**S3（ストレージ）**
- バケット: `daru-pdf-documents`, `daru-pdf-previews`, `daru-pdf-crops`, `daru-pdf-outputs`
- ライフサイクルポリシー: 30日後にGlacier、90日後に削除（設定可能）

**RDS（オプション）**
- Supabaseの代替として使用する場合
- インスタンスクラス: db.t3.micro（開発）〜db.t3.medium（本番）
- エンジン: PostgreSQL 15

#### ファイル構成
```
infra/aws/
├── ecs/
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── task-definition.json
│   │   └── service.yaml          # ECSサービス定義
│   ├── orchestrator/
│   │   ├── Dockerfile
│   │   ├── task-definition.json
│   │   └── service.yaml
│   ├── web/
│   │   ├── Dockerfile
│   │   └── s3-cloudfront.yaml    # S3 + CloudFront設定
│   └── services/                 # 各パイプラインサービス
│       ├── ingest/
│       ├── extract/
│       └── ...
├── terraform/                    # Infrastructure as Code（推奨）
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── ecs/
│       ├── elasticache/
│       ├── s3/
│       └── alb/
├── scripts/
│   ├── deploy.sh                 # デプロイスクリプト
│   ├── setup.sh                  # 初期セットアップ
│   └── migrate.sh                # データベースマイグレーション
├── .env.aws.example              # 環境変数テンプレート
└── README.md                     # セットアップ・デプロイ手順
```

#### デプロイ方法

**Terraform使用（推奨）**
```bash
cd infra/aws/terraform
terraform init
terraform plan
terraform apply
```

**AWS CLI使用**
```bash
cd infra/aws/ecs/api
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin ECR_REGISTRY
docker build -t daru-api .
docker tag daru-api:latest ECR_REGISTRY/daru-api:latest
docker push ECR_REGISTRY/daru-api:latest
aws ecs update-service --cluster daru-cluster --service daru-api --force-new-deployment
```

**スクリプト使用**
```bash
cd infra/aws/scripts
./setup.sh                    # 初回セットアップ（リソース作成）
./deploy.sh api               # APIデプロイ
./deploy.sh orchestrator      # Orchestratorデプロイ
./deploy.sh all               # 全サービスデプロイ
```

#### 環境変数（AWS固有）
```bash
# AWS基本設定
AWS_REGION=ap-northeast-1
AWS_ACCOUNT_ID=123456789012
AWS_ECS_CLUSTER=daru-cluster

# ECR
AWS_ECR_REGISTRY=123456789012.dkr.ecr.ap-northeast-1.amazonaws.com

# S3
AWS_S3_BUCKET_DOCUMENTS=daru-pdf-documents
AWS_S3_BUCKET_PREVIEWS=daru-pdf-previews
AWS_S3_BUCKET_CROPS=daru-pdf-crops
AWS_S3_BUCKET_OUTPUTS=daru-pdf-outputs

# ElastiCache (Redis)
AWS_REDIS_ENDPOINT=daru-redis.xxxxx.cache.amazonaws.com
AWS_REDIS_PORT=6379

# ALB
AWS_ALB_DNS_NAME=daru-alb-xxxxx.ap-northeast-1.elb.amazonaws.com

# Supabase（継続利用の場合）
DARU_SUPABASE_URL=https://xxx.supabase.co
DARU_SUPABASE_SERVICE_KEY=xxx
```

#### 受け入れ基準
- Terraform/スクリプトで全リソースが作成される
- 各ECSサービスが正常に起動
- ALB経由でWeb UIとAPIにアクセス可能
- ジョブ作成・実行が正常に動作
- S3へのファイルアップロード・取得が可能

---

## 共通要件

### 環境変数管理
各環境は以下の共通環境変数を使用（環境固有の値は環境変数で注入）：

```bash
# アプリケーション設定（共通）
DARU_DEBUG=false
DARU_API_PREFIX=/api/v1
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.7
DARU_MAX_STEPS_PER_RUN=100

# LLM設定（共通）
DARU_OPENAI_API_KEY=xxx
DARU_OPENAI_MODEL=gpt-4o-mini
DARU_OPENAI_TIMEOUT_SECONDS=120

# Supabase設定（共通、または環境固有DB使用）
DARU_SUPABASE_URL=xxx
DARU_SUPABASE_SERVICE_KEY=xxx
DARU_SUPABASE_ANON_KEY=xxx

# ストレージ設定（環境固有）
# Docker Compose: ローカルパス
# GCP: Cloud Storageバケット名
# AWS: S3バケット名

# キュー設定（環境固有）
# Docker Compose: redis://redis:6379
# GCP: Cloud Memorystoreエンドポイント
# AWS: ElastiCacheエンドポイント
```

### ヘルスチェック
全サービスは`/health`エンドポイントを提供：
- `GET /health`: 200 OK + `{"status": "healthy"}`
- 依存サービス（DB、Redis）の接続確認を含む

### ロギング
- 構造化ログ（JSON形式）を出力
- ログレベル: INFO（本番）、DEBUG（開発）
- ログ出力先:
  - Docker Compose: stdout/stderr（Docker logs）
  - GCP: Cloud Logging
  - AWS: CloudWatch Logs

### モニタリング（基本）
- メトリクス収集:
  - Docker Compose: オプション（Prometheus等）
  - GCP: Cloud Monitoring
  - AWS: CloudWatch Metrics
- アラート設定:
  - サービスダウン
  - エラー率上昇
  - レスポンスタイム悪化

### セキュリティ
- 認証: Supabase Auth（JWT検証）
- ネットワーク:
  - Docker Compose: 内部ネットワーク分離
  - GCP: VPC、Cloud Armor（オプション）
  - AWS: VPC、Security Groups、WAF（オプション）
- シークレット管理:
  - Docker Compose: `.env`ファイル（gitignore）
  - GCP: Secret Manager
  - AWS: Secrets Manager

### データベースマイグレーション
各環境でSupabaseマイグレーションを実行：
```bash
# 共通スクリプト
infra/scripts/migrate.sh
```

## デプロイメント戦略

### ブルー・グリーンデプロイメント（推奨）
- GCP: Cloud Runのトラフィック分割機能
- AWS: ECSのブルー・グリーンデプロイメント
- Docker Compose: 手動切り替え（開発環境）

### ロールバック
- 各環境で前バージョンへの即時ロールバックが可能
- GCP: Cloud Runのリビジョン管理
- AWS: ECSの前タスク定義への切り替え
- Docker Compose: イメージタグ指定

## 受け入れ基準（全体）

### Docker Compose
- ✅ `docker-compose up`で全サービスが起動
- ✅ 各サービスの`/health`が応答
- ✅ Web UIからAPI経由でジョブ作成・実行が可能

### GCP
- ✅ Terraform/スクリプトで全リソースが作成
- ✅ 各Cloud Runサービスが正常起動
- ✅ ロードバランサー経由でアクセス可能
- ✅ ジョブ作成・実行が正常動作
- ✅ Cloud Storageへのファイル操作が可能

### AWS
- ✅ Terraform/スクリプトで全リソースが作成
- ✅ 各ECSサービスが正常起動
- ✅ ALB経由でアクセス可能
- ✅ ジョブ作成・実行が正常動作
- ✅ S3へのファイル操作が可能

### 独立性
- ✅ 各環境は独立してデプロイ可能
- ✅ 環境間で設定ファイルを共有しない
- ✅ 一つの環境の変更が他環境に影響しない

## マイルストーン

1. **MVP: Docker Compose**
   - `docker-compose.yml`作成
   - 全サービスをDocker Composeで起動
   - 基本動作確認

2. **GCP環境構築**
   - Terraform/スクリプトでリソース作成
   - Cloud Runサービスデプロイ
   - 基本動作確認

3. **AWS環境構築**
   - Terraform/スクリプトでリソース作成
   - ECSサービスデプロイ
   - 基本動作確認

4. **最適化・ドキュメント**
   - デプロイスクリプトの改善
   - ドキュメント整備
   - モニタリング・アラート設定
