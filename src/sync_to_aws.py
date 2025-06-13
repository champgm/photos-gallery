import subprocess
import sys


def run_command(command):
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 1:
        print("Usage: python src/scripts/sync_to_aws.py <bucket_name>")
        sys.exit(1)

    s3bucketname = sys.argv[1]

    print(f"s3bucketname {s3bucketname}")

    # Sync directories with AWS
    print("Syncing with AWS...")
    # These are taken care of in the frontend repo
    # run_command(f"aws s3 sync --follow-symlinks js s3://{s3bucketname}/js/")
    # run_command(f"aws s3 sync --follow-symlinks css s3://{s3bucketname}/css/")
    # run_command(f"aws s3 cp index.html s3://{s3bucketname}/index.html")
    print("Syncing image thumbnails...")
    run_command(
        # Do this normally:
        # f"aws s3 sync --follow-symlinks thumbnail s3://{s3bucketname}/thumbnail/"
        
        # Cleanup with "--delete", don't normally do this:
        f"aws s3 sync --delete --follow-symlinks thumbnail s3://{s3bucketname}/thumbnail/"
    )
    print("Syncing images...")
    run_command(
        # Do this normally:
        # f'aws s3 sync --follow-symlinks --exclude "*.json" images s3://{s3bucketname}/images/'
        
        # Cleanup with "--delete", don't normally do this:
        f'aws s3 sync --delete --follow-symlinks --exclude "*.json" images s3://{s3bucketname}/images/'
    )
    
    print("Syncing video thumbnails...")
    run_command(
        # f"aws s3 sync --follow-symlinks video_thumbnail s3://{s3bucketname}/video_thumbnail/"
        f"aws s3 sync --delete --follow-symlinks video_thumbnail s3://{s3bucketname}/video_thumbnail/"
    )
    print("Syncing videos...")
    run_command(
        # f'aws s3 sync --follow-symlinks --exclude "*.json" videos s3://{s3bucketname}/videos/'
        f'aws s3 sync --delete --follow-symlinks --exclude "*.json" videos s3://{s3bucketname}/videos/'
    )
    print("Uploading CSVs...")
    run_command(f"aws s3 cp photos.csv s3://{s3bucketname}/photos.csv")
    run_command(f"aws s3 cp videos.csv s3://{s3bucketname}/videos.csv")


if __name__ == "__main__":
    main()
