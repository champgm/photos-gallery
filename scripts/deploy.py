from botocore.exceptions import ClientError
import boto3
import click
import os
import subprocess
import time


def get_script_directory() -> str:
    script_path = __file__
    full_path = os.path.realpath(script_path)
    script_dir = os.path.dirname(full_path)
    return script_dir


def get_template_path() -> str:
    script_directory = get_script_directory()
    parent_directory = os.path.dirname(script_directory)
    infra_directory = os.path.join(parent_directory, "infra")
    template_path = os.path.join(infra_directory, "photo_bucket.yaml")
    return template_path


# def deploy_cloudformation_stack(stack_name, bucket_name):
#     # Define the path to your CloudFormation template file
#     script_directory = get_script_directory()
#     parent_directory = os.path.dirname(script_directory)
#     infra_directory = os.path.join(parent_directory, "infra")
#     template_path = os.path.join(infra_directory, "photo_bucket.yaml")

#     # Build the CLI command as a list of arguments
#     cli_command = [
#         "aws",
#         "cloudformation",
#         "create-stack",
#         "--stack-name",
#         stack_name,
#         "--template-body",
#         f"file://{template_path}",
#         "--parameters",
#         f"ParameterKey=BucketName,ParameterValue={bucket_name}",
#         "--capabilities",
#         "CAPABILITY_IAM",
#     ]

#     # Execute the command
#     try:
#         subprocess.run(cli_command, check=True)
#         print(f"Stack '{stack_name}' deployment initiated successfully.")
#     except subprocess.CalledProcessError as e:
#         print(f"Failed to deploy stack '{stack_name}'. Error: {e}")


def get_console_url(region_name, stack_id):
    return f"https://console.aws.amazon.com/cloudformation/home?region={region_name}#/stacks/stackinfo?stackId={stack_id}"


def track_stack_progress(cf, region_name, stack_name):
    stack_url = get_console_url(region_name, stack_name)
    print(f"Tracking stack progress, URL to CloudFormation console: {stack_url}")
    while True:
        try:
            response = cf.describe_stacks(StackName=stack_name)
            stack = response["Stacks"][0]
            status = stack["StackStatus"]
            print(f"Current stack status: {status}")
            if status.endswith(("COMPLETE", "FAILED")):
                break
        except ClientError as e:
            print(f"Error tracking stack progress: {e}")
            break
        time.sleep(10)
    print(f"Done, CloudFormation URL is: {stack_url}")


def deploy_cloudformation_stack(stack_name, bucket_name):
    # Create a CloudFormation client
    cf = boto3.client("cloudformation")
    region_name = cf.meta.region_name  # Get the region name from the client

    # Define the CloudFormation template
    template_path = get_template_path()
    with open(template_path, "r") as file:
        template_body = file.read()

    # Create the CloudFormation stack
    try:
        cf.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=[
                {"ParameterKey": "BucketName", "ParameterValue": bucket_name},
            ],
            Capabilities=["CAPABILITY_IAM"],
        )
        print(
            f"Stack '{stack_name}' creation initiated."
        )
        track_stack_progress(cf, region_name, stack_name)
    except ClientError as e:
        print(f"Failed to create stack '{stack_name}'. Error: {e}")
        return
    


@click.command()
@click.option("--stack-name", required=True, help="Name for CloudFormation stack", default="photo-bucket")
@click.option("--bucket-name", required=True, help="Name of S3 bucket to create")
def main(stack_name: str, bucket_name: str):
    deploy_cloudformation_stack(stack_name, bucket_name)


if __name__ == "__main__":
    main()
