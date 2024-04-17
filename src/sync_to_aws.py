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
    run_command(f"aws s3 sync --follow-symlinks js s3://{s3bucketname}/js/")
    run_command(f"aws s3 sync --follow-symlinks css s3://{s3bucketname}/css/")
    run_command(f"aws s3 cp index.html s3://{s3bucketname}/index.html")
    run_command(f"aws s3 cp photos.csv s3://{s3bucketname}/photos.csv")
    print("Syncing thumbnails...")
    run_command(
        f"aws s3 sync --follow-symlinks thumbnail s3://{s3bucketname}/thumbnail/"
    )
    print("Syncing images...")
    run_command(
        f'aws s3 sync --follow-symlinks --exclude "*.json" images s3://{s3bucketname}/images/'
    )


if __name__ == "__main__":
    main()
