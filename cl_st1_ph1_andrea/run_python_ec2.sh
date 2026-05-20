#!/usr/bin/env bash
set -euo pipefail

# Usage examples:
#   # Simple: run a script with no extra args
#   nohup bash run_python_ec2.sh my_script.py > process_output.log 2>&1 &
#
#   # With script arguments
#   nohup bash run_python_ec2.sh dummy.py --test > process_output.log 2>&1 &
#
#   # Whisper Large v3 full transcription run
#   nohup bash run_python_ec2.sh \
#       transcribe_commercials_whisper.py \
#           --no-test-mode \
#   > process_output.log 2>&1 &
#
#   # Debug without stopping the EC2 instance on exit
#   STOP_INSTANCE_ON_EXIT=false bash run_python_ec2.sh \
#       transcribe_commercials_whisper.py \
#           --test-limit 2
#
#   # Tail logs in another shell
#   tail -f process_output.log
#   tail -f corpus/04_transcripts/transcribe_commercials_whisper.log

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONDA_ENV_NAME="whisper_lg_v3"
CONDA_SH="${HOME}/miniconda3/etc/profile.d/conda.sh"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Whether to request EC2 instance stop when this script exits.
# Default: true.
# Disable for debugging:
#   STOP_INSTANCE_ON_EXIT=false bash run_python_ec2.sh ...
STOP_INSTANCE_ON_EXIT="${STOP_INSTANCE_ON_EXIT:-true}"

# SNS topic to notify when the instance is about to be stopped.
# Ensure the instance role has sns:Publish permission on this ARN.
# Leave empty to disable SNS notification:
#   SNS_TOPIC_ARN=""
SNS_TOPIC_ARN="arn:aws:sns:sa-east-1:849468635108:ec2-stop-notifications"
SNS_REGION="sa-east-1"

# Will be set in main(), used for notifications.
SCRIPT_INVOCATION=""


# ---------------------------------------------------------------------------
# Python runner
# ---------------------------------------------------------------------------

run_python_program() {
  if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <python_program> [args...]" >&2
    exit 1
  fi

  local python_program="$1"
  shift
  local python_args=("$@")

  if [[ ! -f "$CONDA_SH" ]]; then
    echo "Error: conda.sh not found at: $CONDA_SH" >&2
    echo "Update CONDA_SH in this script to match your Miniconda/conda installation." >&2
    exit 1
  fi

  # Conda activation scripts may reference unset variables.
  # Temporarily disable nounset while sourcing conda and activating the environment.
  set +u
  # shellcheck disable=SC1090
  source "$CONDA_SH"
  conda activate "$CONDA_ENV_NAME"
  set -u

  if [[ "${CONDA_DEFAULT_ENV:-}" != "$CONDA_ENV_NAME" ]]; then
    echo "Error: conda environment '$CONDA_ENV_NAME' not activated!" >&2
    exit 1
  fi

  # Ensure CUDA runtime libraries installed in the conda environment are visible.
  # This is required by faster-whisper/CTranslate2 for GPU inference.
  export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"

  # Run from the directory where this launcher script lives so relative corpus
  # paths such as corpus/00_sources and corpus/03_audio resolve correctly.
  cd "$PROJECT_DIR"

  echo "Running in project directory: $PROJECT_DIR"
  echo "Conda environment: ${CONDA_DEFAULT_ENV}"
  echo "Python executable: $(command -v python)"
  echo "Python version: $(python --version)"
  echo "Programme: $python_program"
  echo "Arguments: ${python_args[*]:-}"
  echo "STOP_INSTANCE_ON_EXIT: $STOP_INSTANCE_ON_EXIT"

  # -u for unbuffered output, so logs stream immediately under nohup.
  python -u "$python_program" "${python_args[@]}"

  conda deactivate || true
}


# ---------------------------------------------------------------------------
# EC2 + SNS helper functions
# ---------------------------------------------------------------------------

get_imds_token() {
  curl -fsS -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"
}


imds_get_with_token() {
  local token path
  token="$1"
  path="$2"

  curl -fsS -H "X-aws-ec2-metadata-token: $token" \
    "http://169.254.169.254/latest/${path}"
}


notify_shutdown() {
  # Sends a notification to SNS that this instance is being stopped.
  # Expects:
  #   $1 = instance_id
  #   $2 = instance region

  local instance_id="$1"
  local instance_region="$2"

  # SNS notification is optional. If not configured or aws CLI is missing,
  # skip without failing the transcription run.
  if [[ -z "${SNS_TOPIC_ARN:-}" ]]; then
    echo "Info: SNS_TOPIC_ARN not set; skipping SNS notification." >&2
    return 0
  fi

  command -v aws >/dev/null 2>&1 || {
    echo "Warning: aws CLI not found; skipping SNS notification." >&2
    return 0
  }

  local sns_region="${SNS_REGION:-}"
  if [[ -z "$sns_region" ]]; then
    # Fallback: try to extract region from ARN.
    # ARN format: arn:partition:service:region:account-id:resource
    sns_region="$(echo "$SNS_TOPIC_ARN" | awk -F: '{print $4}')"
  fi

  if [[ -z "$sns_region" ]]; then
    echo "Warning: SNS region could not be determined; skipping SNS notification." >&2
    return 0
  fi

  local subject="EC2 instance stopping: ${instance_id}"
  local message
  message=$(
    cat <<EOF
EC2 instance is being stopped.

Instance ID     : ${instance_id}
Instance Region : ${instance_region}
SNS Region      : ${sns_region}

Script invocation:
${SCRIPT_INVOCATION}
EOF
  )

  aws sns publish \
    --region "$sns_region" \
    --topic-arn "$SNS_TOPIC_ARN" \
    --subject "$subject" \
    --message "$message" >/dev/null 2>&1 || {
      echo "Warning: failed to publish shutdown notification to SNS." >&2
    }
}


stop_instance() {
  # Prerequisites when used on EC2:
  # - aws CLI installed
  # - IAM role attached that allows:
  #   - ec2:StopInstances on this instance
  #   - sns:Publish on the configured SNS topic, if SNS is enabled

  command -v aws >/dev/null 2>&1 || {
    echo "Warning: aws CLI not found; not stopping instance." >&2
    return 0
  }

  local token instance_id region

  token="$(get_imds_token)" || {
    echo "Warning: failed to get IMDS token; not stopping instance." >&2
    return 0
  }

  instance_id="$(imds_get_with_token "$token" "meta-data/instance-id")" || {
    echo "Warning: failed to get instance ID; not stopping instance." >&2
    return 0
  }

  region="$(imds_get_with_token "$token" "meta-data/placement/region")" || true

  if [[ -z "${region:-}" ]]; then
    region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
  fi

  if [[ -z "${region:-}" ]]; then
    echo "Warning: AWS region could not be determined; not stopping instance." >&2
    return 0
  fi

  # Try to send SNS notification first. Non-fatal if it fails.
  notify_shutdown "$instance_id" "$region" || true

  aws ec2 stop-instances \
    --region "$region" \
    --instance-ids "$instance_id" >/dev/null || true

  echo "Instance $instance_id stop requested in region $region."
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  # Capture how this script was invoked for the SNS message.
  SCRIPT_INVOCATION="$0 $*"

  # Automatically stop the instance on exit when enabled.
  # Disable for debugging with:
  #   STOP_INSTANCE_ON_EXIT=false bash run_python_ec2.sh ...
  if [[ "$STOP_INSTANCE_ON_EXIT" == "true" ]]; then
    trap stop_instance EXIT
  fi

  run_python_program "$@"
}


main "$@"