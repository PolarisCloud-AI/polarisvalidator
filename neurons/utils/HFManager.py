import json
from huggingface_hub import HfApi, Repository
import os
from datetime import datetime
from huggingface_hub import HfApi, Repository,hf_hub_download
from datetime import datetime
from typing import List, Dict, Optional
def commit_to_central_repo(model_repo: str, metrics: dict, miner_uid: int):
    """
    Upload metrics and model information to a central Hugging Face repository using the Hub API.
    
    :param hf_token: Hugging Face API token
    :param central_repo: Name of the central repository to upload to
    :param model_repo: URL of the model repository
    :param metrics: Dictionary containing training metrics
    :return: URL of the uploaded file in the central repository
    """
    central_repo = "Tobius/yogpt_v1"
    hf_token='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'
    api = HfApi(token=hf_token)
    
    # Ensure the central repository exists, create if it doesn't
    try:
        api.repo_info(repo_id=central_repo)
    except Exception:
        api.create_repo(repo_id=central_repo, private=True)
    
    # Create a unique filename for this upload
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"training_run_{timestamp}.json"

    # Prepare the data to be uploaded
    data = {
        "model_repo": model_repo,
        "metrics": metrics,
        "timestamp": timestamp,
        "miner_uid": miner_uid
    }

    # Write the data to a temporary file
    temp_file_path = f"/tmp/{filename}"
    with open(temp_file_path, "w") as f:
        json.dump(data, f, indent=2)

    # Upload the file to the repository
    api.upload_file(
        path_or_fileobj=temp_file_path,
        path_in_repo=filename,
        repo_id=central_repo,
        commit_message=f"Training run {timestamp}"
    )

    # Clean up the temporary file
    os.remove(temp_file_path)

    # Get the URL of the uploaded file
    file_url = f"https://huggingface.co/{central_repo}/blob/main/{filename}"

    return file_url


def fetch_training_metrics_commits(repo_id: str) -> List[Dict]:
    try:
        token = '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'
        api = HfApi(token=token)
        model_repo_url = f"https://huggingface.co/{repo_id}"
        commits = api.list_repo_commits(repo_id=repo_id, token=token)

        training_metrics = []
        processed_commits = 0

        print(f"Found {len(commits)} total commits in repository")

        for commit in commits:
            try:
                files = api.list_repo_tree(repo_id=repo_id, revision=commit.commit_id, token=token)
                json_files = [f for f in files if f.path.endswith('.json')]

                for json_file in json_files:
                    try:
                        local_path = hf_hub_download(repo_id=repo_id, filename=json_file.path, 
                                                      revision=commit.commit_id, token=token)

                        with open(local_path, 'r') as f:
                            content = f.read()
                            metrics_data = json.loads(content)

                        # Ensure 'metrics' and 'miner_uid' exist in the JSON data
                        if isinstance(metrics_data, dict) and "metrics" in metrics_data:
                            miner_uid = metrics_data.get("miner_uid")
                            job_id = metrics_data["metrics"].get("job_id") if "metrics" in metrics_data else None

                            # Create metrics entry only if miner_uid is present and job_id is found in metrics
                            if miner_uid and job_id:
                                metrics_entry = {
                                    "model_repo": metrics_data.get("model_repo", "unknown"),
                                    "metrics": metrics_data["metrics"],
                                    "miner_uid": miner_uid,
                                    "job_id": job_id,
                                    "timestamp": metrics_data.get("timestamp", "unknown")
                                }

                                training_metrics.append(metrics_entry)
                                processed_commits += 1

                    except json.JSONDecodeError:
                        print(f"Could not decode JSON in file: {json_file.path}")
                        continue

            except Exception as e:
                print(f"Error processing commit {commit.commit_id}: {str(e)}")
                continue

        # Filter out entries that have both miner_uid and job_id
        filtered_metrics = [entry for entry in training_metrics if entry.get('miner_uid') and entry['metrics'].get('job_id')]

        print(f"Successfully processed {processed_commits} commits with valid metrics")
        return filtered_metrics

    except Exception as e:
        print(f"Error fetching commits: {str(e)}")
        return []

