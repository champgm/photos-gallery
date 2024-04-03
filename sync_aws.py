import subprocess
import sys

def run_command(command):
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) < 5:
        print("Usage: python sync_aws.py s3bucketname img-directory thumbnail-directory metadata-file.csv")
        sys.exit(1)

    s3bucketname, img_directory, thumbnail_directory, metadata_file = sys.argv[1:5]

    print(f"s3bucketname {s3bucketname}")
    print(f"img-directory {img_directory}")
    print(f"thumbnail-directory {thumbnail_directory}")
    print(f"metadata-file {metadata_file}")

    # Sync directories with AWS
    print("Syncing with AWS")
    run_command(f'aws s3 sync --follow-symlinks {img_directory} s3://{s3bucketname}/img/')
    run_command(f'aws s3 sync --follow-symlinks {thumbnail_directory} s3://{s3bucketname}/thumbnail/')
    run_command(f'aws s3 sync --follow-symlinks js s3://{s3bucketname}/js/')
    run_command(f'aws s3 sync --follow-symlinks css s3://{s3bucketname}/css/')
    run_command(f'aws s3 cp index.html s3://{s3bucketname}/index.html')
    run_command(f'aws s3 cp {metadata_file} s3://{s3bucketname}/photos.csv')

if __name__ == '__main__':
    main()
