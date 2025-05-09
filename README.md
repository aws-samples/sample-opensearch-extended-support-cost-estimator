# opensearch-extended-support-cost-estimator-script
## Opensearch Extended Support Cost Estimator Scripts

In November 2024, [Amazon OpenSearch Service announced Extended Support for engine versions](https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-opensearch-service-support-engine-versions/), which allows you to continue running your Opensearch domains on a major engine version past its end of standard support date for legacy Elasticsearch versions and OpenSearch Versions at an additional cost. 

These scripts can be used to help estimate the cost of Opensearch Extended Support for Opensearch/Elasticsearch domains in your AWS accounts and organization. This script runs in all AWS regions that are available, and if a region is not enabled in the specific account, that region is skipped. 

These scripts should be run from the payer account of your organization to identify the Opensearch & ElasticSearch clusters in your organization that will be impacted by the extended support and the estimated additional cost for the versions below.

* The end of support schedule for _Elasticsearch_ versions is as follows:

| Software Version	| End of Standard Support	| End of Extended Support |
| ----------------- | ------------------------- | ----------------------- |
| Elasticsearch versions 1.5 and 2.3	| 11/07/2025	| 11/07/2026 |
| Elasticsearch versions 5.1 and 5.5	| 11/07/2025	| 11/07/2026 |
| Elasticsearch versions 5.6	| 11/07/2025	| 11/07/2028 |
| Elasticsearch versions 6.0 to 6.7	| 11/07/2025	| 11/07/2026 |
| Elasticsearch versions 6.8	| Not announced	| 11/07/2028 |
| Elasticsearch versions 7.1 to 7.8	| 11/07/2025	| 11/07/2026 |
| Elasticsearch versions 7.9	| Not announced	| Not announced |
| Elasticsearch versions 7.10	| Not announced	| Not announced |

* The end of support schedule for _OpenSearch_ versions is as follows:

| Software Version	| End of Standard Support	| End of Extended Support |
| ----------------- | ------------------------- | ----------------------- |
| OpenSearch versions 1.0 and 1.2	| 11/07/2025	| 11/07/2026 |
| OpenSearch versions 1.3	| Not announced	| Not announced |
| OpenSearch versions 2.3 to 2.9	| 11/07/2025	| 11/07/2026 |
| OpenSearch versions 2.11 and higher versions	| Not announced	| Not announced |


The scripts will create a CSV file with all the Openserach domains that will be impacted by extended support across all accounts & regions in your organization.

## Calculating extended support charges

Domains running versions under extended support will be charged a flat additional fee/Normalized Instance Hour (NIH), for example, $0.0065 in the US East (North Virginia) Region. NIH is computed as a factor of the instance size (e.g., medium, large), and the number of instance hours. For example, if you are running an m7g.medium.search instance for 24 hours in the US East (North Virginia) Region, which is priced at $0.068/Instance hour (on-demand), you will typically pay $1.632 ($0.068x24). If you are running a version that is in extended support, you will pay an additional $0.0065/NIH, which is computed as $0.0065 x 24 (number of instance hours) x 2 (size normalization factor; 2 for medium-sized instances), which comes to $0.312 for extended support for 24 hours. The total amount you will pay for 24 hours will be a sum of the standard instance usage cost and the extended support cost, which is $1.944 ($1.632+$0.312). The table [here](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html#calculating-charges) shows the normalization factor for various instance sizes in OpenSearch Service.

These scripts provide the following benefits:
* Streamlined identification: Quickly identify all Amazon Opensearch domains enabled for Extended Support across your entire AWS organization and all regions in one go.
* Enhanced visibility and cost awareness: Easily calculate the total yearly cost of extended support for eligible instances, gaining insight into cost implications and enabling informed decision-making to optimize expenses, maximize savings, and ensure timely action and compliance.
* Time-saving automation: Eliminate manual effort by automating the process of listing Opensearch & ElasticSearch domains, saving valuable time for your team. Run the script for a single account, a list of accounts or for the entire organization.
* Proactive management: Stay ahead of extended support deadlines by proactively identifying instances requiring attention, minimizing potential disruptions.


## Current Challenges
1. Opensearch & Elasticsearh versions on extended support are hardcoded currently. Fix the function to dynamically lookup AOS Extended Support versions from AWS documentation or Pricing API if supported, so that future versions can be included.
2. Extended support costs are scraped from the Opensearch pricing page. However, this might break if the HTML code of that page changes, whihc happens frequently.
        The alternatives are:
          1/ hard code the current regional proce for extended support in a file, which will/can get outdated 
          2/ dynamically get the Opensearch Extended Support costs using teh AWS Pricing API - however, the Pricing API doesn't yet return extended support costs for Opensearch. 

## Security and Access Considerations

This script runs locally on your computer and may store sensitive domain information in the output files. Please ensure you follow your organization's security policies regarding data handling and storage of AWS resource information. Consider removing output files after analysis if they are no longer needed.

While the script can run for all accounts in your entire AWS Organization, some organizations may have security policies that restrict access to the management account. In such cases, you can still run the script on individual accounts where you have appropriate access permissions.

This tool follows the AWS Shared Responsibility Model - while AWS manages security of the cloud infrastructure, security of your local environment and handling of the output data is your responsibility. Ensure you have appropriate controls in place to protect any sensitive information generated by this script.


## Prerequisites

1. Download and install [Python 3](https://www.python.org/downloads/).

2. Ensure that you have an IAM principal in your payer/management account that has at least the following IAM permissions:
> NOTE: The script does NOT create these roles/policies in your management account. It is assumed that a user with these permissions already granted to them will run the steps listed here.

```
"organizations:ListAccounts",
"organizations:DescribeOrganization",

"sts:AssumeRole",

"cloudformation:CreateStackSet",
"cloudformation:UpdateStackSet",
"cloudformation:DeleteStackSet",
"cloudformation:ListStackSetOperationResults",
"cloudformation:ListStackInstances",
"cloudformation:StopStackSetOperation"
"cloudformation:CreateStackInstances",
"cloudformation:UpdateStackInstances",
"cloudformation:DeleteStackInstances",

"es:ListDomainNames",
"es:DescribeElasticsearchDomains"
```
These are the minimum permissions needed to create and execute the cloudformation stack/stack-set across the management & all linked accounts in your AWS Organizations. In addition, this also includes the permissions needed to read Amazon Opensearch domain details used by the script. You will be using this IAM principal to configure AWS credentials before running the scripts.

## Step 1: Clone the repo

1. On your laptop, clone the project in a local directory
    ```
    git clone <Repo Link>
    ```

2. Navigate into the project
    ```
    cd openserach_extended_support_cost_estimator
    ```

## Step 2: Create the CloudFormation StackSets

Follow this procedure to create CloudFormation StackSets. The stack set creates an IAM role named *AOSExtendedSupportCostEstimatorRole*
across all member accounts of your organization. This IAM role will be assumed by the payer account during the script execution
to query affected Opensearch & ElasticSearch instances in the member accounts.

**Note**:
You only need to complete this step once from the management account (payer account).

**Important**:
Running a stack set does not execute the stack on the management account itself, it will only run on all child accounts. 
To run on management account, in case there are Opensearch domains in it, run it as a standalone cloudformation stack first, and then run a stack set for the Organization.


**To create the CloudFormation StackSets**

1. Sign in to the AWS Management Console of the payer/management account as a user assigned the minimum IAM permissions as mentioned in Prerequisites step #2 above.
2. In the CloudFormation console, select StackSets in the left navigation panel and create a stack set with the template file that you downloaded. Provide the Management Account ID as the input parameter when asked on the console.
3. For the template, use the [aos_extended_support_cost_estimator_role.yaml](opensearch_extended_support_cost_estimator/cfn_template/aos_extended_support_cost_estimator_role.yaml) template file in the cfn_template directory of the cloned repo.
4. For Region, select any one region only (eg us-east-1). You only need to select a single region as the cloudformation template creates a single IAM role, which is a global service.

For more information, see [Creating a stack set on the AWS CloudFormation console](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-getting-started-create.html)
in the AWS CloudFormation User Guide.

After CloudFormation creates the stack set, each member account in your organization has *AOSExtendedSupportCostEstimatorRole* IAM role.
The IAM role contains the following permissions:
```
"es:ListDomainNames",
"es:DescribeElasticsearchDomains"
```

## Step 3: Set up the environment

Execute the following steps from the directory that was created after cloning the project. 

1. [**ONLY applicable to Debian/Ubuntu systems**] Install python3-venv

   This command should only be run if you are using Debian/Ubuntu systems. For all other systems, skip this and
   move to 4.
   ```
   sudo apt install -y python3-venv
   ```

2. Setup virtualenv
    ```
    python3 -m venv venv
    ```

3. Activate virtualenv
    ```
    source venv/bin/activate
    ```

4. Install dependencies
    ```
    pip install -r requirements.txt
    ```

5. Navigate to directory containing the scripts
    ```
    cd scripts/
    ```

6. Configure the credentials using AWS CLI. You can read more about how to do this [here](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#interactive-configuration).
   Credentials can be configured in multiple ways. Regardless of the method that you choose, you must have both **AWS credentials**
   and an **AWS Region** set before running the scripts. The simplest way is to do this in an interactive manner using AWS CLI
   and running `aws configure` command to set up your credentials and default region. Follow the prompts, and it will generate
   configuration files in the correct locations for you.

**Note:**
Specifying incorrect region can cause errors during script execution. For e.g. when running the script in China regions,
if the region is set to *us-east-1* you will see errors like - `The security token included in the request is invalid`.
For China regions, the region value should be either *cn-north-1* or *cn-northwest-1*.


## Step 4: Identify the affected Opensearch & ElasticSearch instances

To identify affected Openserach & ElasticSearch domains run the `find_aos_extended_support_instances.py` script

The script supports the following arguments:
```
$ python3 find_aos_extended_support_instances.py -h

usage: find_aos_extended_support_instances.py [-h] [-a ACCOUNTS | --accounts-file ACCOUNTS_FILE | --all] [--regions-file REGIONS_FILE] [--exclude-accounts EXCLUDE_ACCOUNTS] [--generate-accounts-file] [--generate-regions-file]

optional arguments:
  -h, --help            show this help message and exit
  -a ACCOUNTS, --accounts ACCOUNTS
                        comma separated list of AWS account IDs
  --accounts-file ACCOUNTS_FILE
                        Absolute path of the CSV file containing AWS account IDs
  --all                 runs script for the entire AWS Organization
  --regions-file REGIONS_FILE
                        Absolute path of the CSV file containing specific AWS regions to run the script against
  --exclude-accounts EXCLUDE_ACCOUNTS
                        comma separated list of AWS account IDs to be excluded, only applies when --all flag is used
  --generate-accounts-file
                        Creates a `accounts.csv` CSV file containing all AWS accounts in the AWS Organization
  --generate-regions-file
                        Creates a `regions.csv` CSV file containing all AWS regions
``` 

The details about using these input parameters are below:

* --all – Scans all member accounts in your organization.

```
python find_aos_extended_support_instances.py --all
```

* --accounts – Scans a subset of member accounts in your organization.

```
python find_aos_extended_support_instances.py --accounts 111122223333,444455556666,777788889999
```

* --accounts-file – Absolute path to the CSV file containing a subset of member accounts in your organization that needs
  to be scanned. The CSV file should have no headers and contain 12 digit AWS Account IDs in the first column of the file.

```
python find_aos_extended_support_instances.py --accounts-file /path/to/accounts_file.csv
```

* --exclude-accounts – Excludes specific member accounts in your organization. Can only be used with --all

```
python find_aos_extended_support_instances.py --all --exclude-accounts 111111111111,222222222222,333333333333
```

* If no argument is provided, script runs for the current account (payer account)

```
python find_aos_extended_support_instances.py
```

* --generate-accounts-file - Creates a `accounts.csv` CSV file in the current directory containing all AWS accounts in the AWS Organization. You can then edit/remove the accounts that you do not need from the CSV and use this file as a script input. Note: using this option will ignore all other script parameters and exit after generating the file.

```
python find_aos_extended_support_instances.py --generate-accounts-file
python find_aos_extended_support_instances.py --accounts-file /path/to/accounts.csv
```

* --generate-regions-file - Creates a `regions.csv` CSV file in the current directory containing all AWS regions. You can then edit/remove the regions that you do not need from the CSV and use this file as a script input. Note: using this option will ignore all other script parameters and exit after generating the file.

```
python find_aos_extended_support_instances.py --generate-regions-file
python find_aos_extended_support_instances.py --all --regions-file /path/to/regions.csv
```

After you run the script, it creates a CSV file in the <pwd>/output/aos_extended_support_instances_<*Timestamp*> format in the `output` directory.

## Output
The script creates a folder called `output/` in the same directory where the script runs from on first run. Subsequently, it uses the `output/` folder to save the results.

The final output of the script is a csv called `./output/opensearch_extended_support_instances-<timestamp>.csv` in the same directory where the script is run from. The headers of the csv are: 
```
AccountId                    : The AWS account ID
Region                       : The Region in which the Opensearch/ElasticSearch instance is in, eg `us-east-1`
RegionName                   : The full AWS region name, eg `US East (N. Virginia)`
DomainName                   : Opensearch/Elasticsearch Domain name
ARN                          : ARN of the Oepensearch domain
EngineVersion                : Opensearch/Elasticsearch version, e.g. OpenSearch_1.0, Elasticsearch_1.5
DedicatedMasterType          : Instance type of Master nodes
DedicatedMasterCount         : Number of Master nodes
Normalization Factor (Master Nodes) : The NF for Master node instance size, e.g. medium = 2, xlarge = 8
InstanceType                 : Instance type of data/instance nodes
InstanceCount                : Number of Data/Instance nodes
Normalization Factor (Data Nodes)         : The NF for instance size, e.g. medium = 2, xlarge = 8
WarmType                     : Instance type of UltraWarm nodes, if used.
WarmCount                    : Number of UltraWarm Nodes
Normalization Factor (Ultrawarm Nodes) : The NF for UltraWarm instance size, e.g. medium = 2, xlarge = 8
CoordinatorNodeType          : Instance type of Coordinator nodes, if used.
CoordinatorNodeCount         : Number of Coordinator nodes
Normalization Factor (Coordinator Nodes): The NF for Coordinator node instance size, e.g. medium = 2, xlarge = 8
Regional Price Per NIH       : Price per NIH in the region 
End of Standard Support      : Date when Standard support ends
End of Extended Support      : Date when Extended support ends
Yearly Extended Support Cost : Yearly cost of being on extended support 
```

**Note** - the Yearly cost is just the additional cost of extended support charges, it DOES NOT include the regular cost of running the opensearch cluster.


## Cleanup
If you do not need to run the script again in future, you can simply delete the project folder from your laptop.

To remove the IAM role that was created using the CloudFormation Stack/StackSets, follow the steps to remove the stacks and then delete the stack set, as per the [AWS Documentation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-getting-started.html). This will delete the IAM role from your linked accounts. If the cloudformation stack set was deployed for the organization, then you will need the AWS Organizations OU-ID when deleting stack from the stack set. You can obtain it from the AWS Organizations console. 

If the Cloudformation stack fails to delete for any reason, please perform a manual cleanup of the *AOSExtendedSupportCostEstimatorRole* IAM role from the accounts where the stack failed to delete.

**NOTE:** Make sure you [Delete stack instances from your stack set](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stackinstances-delete.html) before trying to [Delete the stack set](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-delete.html) itself. 

## Troubleshooting

### IAM role “AOSExtendedSupportCostEstimatorRole” not created in all member accounts of an AWS Organization

This issue mostly occurs when you create a stack instead of a **“stack set”** in [step 2](README.md#step-2-create-the-cloudformation-stack-set)
of this procedure. If you create a stack, this only creates the required IAM role in the management account.
You must create a CloudFormation “stack set” in the management account of your AWS organization. Using a stack set
ensures that the required IAM role is created for all member accounts in the organization. Please see this AWS Documentation link to get started with [AWS CloudFormation Stack Sets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-getting-started.html)

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.