# Workload Identity Federation for GitHub Actions
#
# Enables keyless authentication from GitHub Actions to GCP.
# GitHub Actions obtains an OIDC token and exchanges it for
# short-lived GCP credentials via the Workload Identity Pool.
#
# SECURITY: attribute_condition restricts to main branch only.
# PR workflows should NOT get GCP credentials.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions Pool"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Restrict to specific repo AND protected refs (main branch + tags)
  attribute_condition = "assertion.repository == \"${var.github_repo}\" && (assertion.ref == \"refs/heads/main\" || assertion.ref.startsWith(\"refs/tags/\"))"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Service account used by GitHub Actions
resource "google_service_account" "github_actions" {
  project      = var.project_id
  account_id   = "github-actions-deployer"
  display_name = "GitHub Actions Deployer"
  description  = "Service account for CI/CD via GitHub Actions"
}

# IAM roles for the service account -- scoped to minimum required
resource "google_project_iam_member" "roles" {
  for_each = toset([
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/secretmanager.viewer",
    "roles/iam.serviceAccountUser",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# State bucket access -- granted at bucket level, not project level
# The bucket name is passed as a variable so we can scope precisely
resource "google_storage_bucket_iam_member" "state_bucket_read" {
  count  = var.state_bucket_name != "" ? 1 : 0
  bucket = var.state_bucket_name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.github_actions.email}"
}

# Allow GitHub Actions to impersonate the service account
resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
