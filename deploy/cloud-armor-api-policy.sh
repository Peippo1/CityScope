#!/usr/bin/env bash
set -euo pipefail

: "${CITYSCOPE_PROJECT:?Set CITYSCOPE_PROJECT to the GCP project id}"
: "${CITYSCOPE_BACKEND_SERVICE:?Set CITYSCOPE_BACKEND_SERVICE to the external HTTPS load-balancer backend service}"

policy="cityscope-api-public"
gcloud compute security-policies create "$policy" --project "$CITYSCOPE_PROJECT" --description="CityScope public API edge protections" 2>/dev/null || true
rule_args=(
  1000
  --project "$CITYSCOPE_PROJECT"
  --security-policy "$policy"
  --expression='request.path == "/investigate" && request.method == "POST"'
  --action=throttle
  --rate-limit-threshold-count=12
  --rate-limit-threshold-interval-sec=300
  --conform-action=allow
  --exceed-action=deny-429
  --enforce-on-key=IP
  --description="Bound public Gemini-backed investigations"
)
gcloud compute security-policies rules create "${rule_args[@]}" \
  2>/dev/null || gcloud compute security-policies rules update 1000 \
  --project "$CITYSCOPE_PROJECT" \
  --security-policy "$policy" \
  --expression='request.path == "/investigate" && request.method == "POST"' \
  --action=throttle \
  --rate-limit-threshold-count=12 \
  --rate-limit-threshold-interval-sec=300 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Bound public Gemini-backed investigations"
gcloud compute backend-services update "$CITYSCOPE_BACKEND_SERVICE" --global --project "$CITYSCOPE_PROJECT" --security-policy "$policy"
