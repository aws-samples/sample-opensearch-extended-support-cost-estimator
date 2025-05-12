# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import sys
import uuid
import json
import boto3
import argparse
import threading 
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from botocore.exceptions import ClientError

import pandas as pd

from utils.utils import (
    is_china_region, 
    validate_if_being_run_by_payer_account, 
    validate_org_accounts,
    get_all_org_accounts,
    read_accounts_from_file,
    write_accounts_to_file,
    write_regions_to_file
) 

from utils.utils import ValidationException
from utils.log import get_logger
from utils.constants import MEMBER_ACCOUNT_ROLE_NAME

from utils.aos_mappings import (
    is_extended_support_eligible,
    get_aos_extended_support_mapping,
    get_aos_instance_mapping,
    get_opensearch_extended_support_cost,
    get_aos_regions
)

LOGGER = get_logger(__name__)

''' Build some local caches for -  
    1. Opensearch Regions
    2. Opensearch Instance Mapping
    3. Opensearch Extended Support Versions
    4. Opensearch Extended Support Pricing
    5. Cache for storing processed account IDs  
'''
REGIONS = {}
AOS_INSTANCE_MAPPING = {}
AOS_EXTENDED_SUPPORT_VERSIONS = {}
AOS_EXTENDED_SUPPORT_PRICING = get_opensearch_extended_support_cost()

processed_accounts = []
try:
    # Try to load processed accounts from cache file
    with open('.tmp_accounts_cache.json', encoding="utf-8") as f:
        processed_accounts = json.load(f)
        LOGGER.info(f'Found a previous cache file with {len(processed_accounts)} accounts aready processed. Continuing with remaining accounts...')
except:
    pass

# Use a thread lock  
lock = threading.Lock()

# check if `output` directory exists in current working dir, if not create it.
if not os.path.isdir('./output'):
    LOGGER.debug("'output' folder does not exist, creating it now")
    os.makedirs('./output')

# create a filename using today's date time in YY-MM-DD HH-MM format
outfile = f'./output/aos_extended_support_instances-{datetime.now().strftime("%Y-%m-%d %H-%M")}.csv'
LOGGER.info("Outfile name: {}".format(outfile))


def get_aos_client(account_id_, payer_account_, region_, assume_role=MEMBER_ACCOUNT_ROLE_NAME):
    if account_id_ == payer_account_:
        LOGGER.debug("Running for Payer account, returning aos boto3 client")
        aos_client = boto3.client('opensearch', region_name=region_)
    else:
        LOGGER.debug("Running for Linked account, assuming custom role and returning opensearch boto3 client after extracting credentials")
        sts_client = boto3.client('sts')
        partition = sts_client.meta.partition
        assumed_role_object = sts_client.assume_role(
            RoleArn=f'arn:{partition}:iam::{account_id_}:role/{assume_role}',
            RoleSessionName=f'AssumeRoleSession{uuid.uuid4()}'
        )
        credentials = assumed_role_object['Credentials']
        aos_client = boto3.client(
            'opensearch',
            region_name=region_,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )
    return aos_client

def get_aos_domains(aos_client):
    aos_domains = []
    domains = aos_client.list_domain_names()
    try:
        for domain in domains['DomainNames']:
            aos_domains.append(domain)
    except ClientError as err:
        if err.response["Error"]["Code"] == "InvalidClientTokenId":
            LOGGER.error("Received InvalidClientTokenId error - perhaps Region {} is not enabled for the account. Skipping region ...".format(aos_client.meta.region_name))
            raise ClientError("Script can only be run in regions that have been enabled") from err
        else:
            raise err
    except Exception as err:
        LOGGER.error("Failed calling OpenSearch ListDomainNames API")
        raise err
    return aos_domains

def get_opensearch_extended_support_instances(account_id, caller_account):
    global AOS_INSTANCE_MAPPING
    global AOS_EXTENDED_SUPPORT_VERSIONS
    domain_keys = ['DomainName', 'ARN', 'EngineVersion']
    opensearch_extended_support_instances = []

    #### OVERRIDE - FOR TESTING ###
    #REGIONS = {'us-east-1':'US East (N. Virginia)', 'us-west-2': 'US West (Oregon)', 'eu-west-1': 'Europe (Ireland)'}
    #### OVERRIDE - FOR TESTING ###

    for region in REGIONS:
        LOGGER.info(f'Running for account {account_id} in region {region}')
        aos_client = get_aos_client(account_id, caller_account, region)
        
        try: 
            aos_domains = get_aos_domains(aos_client)
            LOGGER.info(f'Found {len(aos_domains)} OpenSearch domains in account {account_id} in region {region}')

            # Need to chunk in group of 5s otherwise describe_domains API throws an error - 
            # 'Please provide a maximum of 5 domain names to describe.'
            LOGGER.debug("Getting domain details in chunks of 5")
            for i in range(0, len(aos_domains), 5):
                domain_names = [domain['DomainName'] for domain in aos_domains[i:i+5]]
                LOGGER.debug(f'Next chunk of 5 Domain names: {domain_names}')
                domain_details = aos_client.describe_domains(DomainNames=domain_names)

                for domain in domain_details['DomainStatusList']:
                    LOGGER.debug(f'Domain: {domain}')
                    # Opensearch versions are of the format OpenSearch_X.Y, whereas Elasticsearch versions just return X.Y
                    aos_version = domain['EngineVersion']
                    if is_extended_support_eligible(aos_version):
                        shortlist_instance = {}
                        shortlist_instance['AccountId'] = account_id
                        shortlist_instance['Region'] = region
                        shortlist_instance['RegionName'] = REGIONS[region]

                        domain_info = {key: domain[key] for key in domain_keys}
                        shortlist_instance.update(domain_info)

                        # Master nodes
                        if 'DedicatedMasterType' in domain['ClusterConfig']:
                            shortlist_instance['DedicatedMasterType'] = domain['ClusterConfig']['DedicatedMasterType']
                            shortlist_instance['DedicatedMasterCount'] = domain['ClusterConfig']['DedicatedMasterCount']

                            # Handle the case where an opensearch instance type is not found in aos_instance_mapping.json (perhaps its a new family/size added)
                            # We will just regenrate the entire mapping by scrapping the AWS Documentation HTML page. 
                            master_instance_size = shortlist_instance['DedicatedMasterType'].split('.')[1]
                            if master_instance_size not in AOS_INSTANCE_MAPPING:
                                LOGGER.error(f'Instance type {shortlist_instance["DedicatedMasterType"]} not found in aos_instance_mapping.json. Regenerating json file from AWS documentation')
                                AOS_INSTANCE_MAPPING = get_aos_instance_mapping()
                                LOGGER.info(f'Updated AOS Instance Mapping: {AOS_INSTANCE_MAPPING}')
                            shortlist_instance['Normalization Factor (Master Nodes)'] = AOS_INSTANCE_MAPPING[master_instance_size]
                        else:
                            shortlist_instance['DedicatedMasterType'] = 'N/A'
                            shortlist_instance['DedicatedMasterCount'] = 0
                            shortlist_instance['Normalization Factor (Master Nodes)'] = 0

                        # Data nodes
                        shortlist_instance['InstanceType'] = domain['ClusterConfig']['InstanceType']
                        shortlist_instance['InstanceCount'] = domain["ClusterConfig"]['InstanceCount']
                        
                        instance_size = shortlist_instance['InstanceType'].split('.')[1]
                        if instance_size not in AOS_INSTANCE_MAPPING:
                            LOGGER.error(f'Instance type {shortlist_instance["InstanceType"]} not found in aos_instance_mapping.json. Regenerating json file from AWS documentation')
                            AOS_INSTANCE_MAPPING = get_aos_instance_mapping()
                            LOGGER.info(f'Updated AOS Instance Mapping: {AOS_INSTANCE_MAPPING}')
                        shortlist_instance['Normalization Factor (Data Nodes)'] = AOS_INSTANCE_MAPPING[instance_size]

                        # Ultrawarm nodes
                        if 'WarmType' in domain['ClusterConfig']:
                            shortlist_instance['WarmType'] = domain['ClusterConfig']['WarmType']
                            shortlist_instance['WarmCount'] = domain['ClusterConfig']['WarmCount']
                            uw_instance_size = shortlist_instance['WarmType'].split('.')[1]
                            if uw_instance_size not in AOS_INSTANCE_MAPPING:
                                LOGGER.error(f'Instance type {shortlist_instance["WarmType"]} not found in aos_instance_mapping.json. Regenerating json file from AWS documentation')
                                AOS_INSTANCE_MAPPING = get_aos_instance_mapping()
                                LOGGER.info(f'Updated AOS Instance Mapping: {AOS_INSTANCE_MAPPING}')
                            shortlist_instance['Normalization Factor (Ultrawarm Nodes)'] = AOS_INSTANCE_MAPPING[uw_instance_size]
                        else:
                            shortlist_instance['WarmType'] = 'N/A'
                            shortlist_instance['WarmCount'] = 0
                            shortlist_instance['Normalization Factor (Ultrawarm Nodes)'] = 0

                        # Dedicated Cooridnator nodes
                        if "NodeOptions" in domain['ClusterConfig']:
                            for option in  domain['ClusterConfig']['NodeOptions']:
                                if option['NodeType'] == 'coordinator':
                                    shortlist_instance['CoordinatorNodeType'] = option['NodeConfig']['Type']
                                    shortlist_instance['CoordinatorNodeCount'] = option['NodeConfig']['Count']
                                    coordinator_instance_size = shortlist_instance['CoordinatorNodeType'].split('.')[1]
                                    if coordinator_instance_size not in AOS_INSTANCE_MAPPING:
                                        LOGGER.error(f'Instance type {shortlist_instance["CoordinatorNodeType"]} not found in aos_instance_mapping.json. Regenerating json file from AWS documentation')
                                        AOS_INSTANCE_MAPPING = get_aos_instance_mapping()
                                        LOGGER.info(f'Updated AOS Instance Mapping: {AOS_INSTANCE_MAPPING}')
                                    shortlist_instance['Normalization Factor (Coordinator Nodes)'] = AOS_INSTANCE_MAPPING[coordinator_instance_size]
                                    break
                                else:
                                    LOGGER.debug(f"Unknown Coordinator NodeType: {option['NodeType']} found in NodeOptions")
                        else:
                            shortlist_instance['CoordinatorNodeType'] = 'N/A'
                            shortlist_instance['CoordinatorNodeCount'] = 0
                            shortlist_instance['Normalization Factor (Coordinator Nodes)'] = 0

                        price_per_nih = AOS_EXTENDED_SUPPORT_PRICING[REGIONS[region]]['price_per_nih']
                        shortlist_instance['Regional Price Per NIH'] = price_per_nih
                        shortlist_instance['End of Standard Support'] = AOS_EXTENDED_SUPPORT_VERSIONS[aos_version]['end_of_standard_support']
                        shortlist_instance['End of Extended Support'] = AOS_EXTENDED_SUPPORT_VERSIONS[aos_version]['end_of_extended_support']
                        
                        
                        # Calculate the total Extended Support Cost - include Data nodes, Master nodes, Corordiantor nodes & Warm nodes
                        ''' See this for an example of calculating extended support charges
                            https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html#calculating-charges
                        '''
                        shortlist_instance['Yearly Extended Support Cost'] = ((shortlist_instance['InstanceCount']        * shortlist_instance['Normalization Factor (Data Nodes)'])        # Data Nodes     
                                                                            + (shortlist_instance['DedicatedMasterCount'] * shortlist_instance['Normalization Factor (Master Nodes)'])      # Master Nodes
                                                                            + (shortlist_instance['CoordinatorNodeCount'] * shortlist_instance['Normalization Factor (Coordinator Nodes)']) # Coordinator Nodes
                                                                            + (shortlist_instance['WarmCount']            * shortlist_instance['Normalization Factor (Ultrawarm Nodes)'])   # Ultrawarm Nodes
                                                                            ) * (price_per_nih * 24 * 365)      # 24 hours * 365 days

                        opensearch_extended_support_instances.append(shortlist_instance)
                        LOGGER.info(f"Instance: {shortlist_instance['DomainName']} is eligible for extended support as its version is: {shortlist_instance['EngineVersion']}")
        except ClientError as e:
            LOGGER.info("Account: {} | Received Exception - message: {}".format(account_id, e))
            LOGGER.info("Account: {} | Perhaps Region {} is not enabled for the account. Skipping region ...".format(account_id, region))
            continue
        except Exception as e:
            LOGGER.info("Account: {} | Received Exception: {}".format(account_id, e))
            raise e

    LOGGER.debug(f'OpenSearch Extended Support Eligible Instances: \n {opensearch_extended_support_instances}')
    
    with lock:
        save_to_csv(opensearch_extended_support_instances)
        processed_accounts.append(account_id)
        with open('.tmp_accounts_cache.json', 'w', encoding="utf-8") as f:
            json.dump(processed_accounts, f)
        
        LOGGER.info(f'Saved eligible Opensearch domains in all regions from {account_id} to csv file, and added account to cache file')


def save_to_csv(opensearch_extended_support_instances):
    if len(opensearch_extended_support_instances) == 0:
        LOGGER.info('No Opensearch domains are eligible for extended support. Not writing anything to CSV for this account')
        return

    df = pd.DataFrame.from_dict(opensearch_extended_support_instances)
    df['Yearly Extended Support Cost'] = df['Yearly Extended Support Cost'].apply(lambda x: "${0:,.2f}".format(x))
    
    #print(df.head())

    df.to_csv(outfile, mode='a', index=False, header=False)

def main():
    global REGIONS
    global AOS_INSTANCE_MAPPING
    global AOS_EXTENDED_SUPPORT_VERSIONS

    LOGGER.info("="*25)
    LOGGER.info("Script Execution Started!")

    args = parse_args()
    sts_client = boto3.client('sts')
    org_client = boto3.client('organizations')
    LOGGER.info("Running with boto client region = %s", sts_client.meta.region_name)
    
    caller_account = sts_client.get_caller_identity()['Account']
    is_china = is_china_region(sts_client)
    validate_if_being_run_by_payer_account(org_client, caller_account)
    LOGGER.info(f'Caller account: {caller_account}')

    REGIONS = get_aos_regions(args.regions_file)
    if args.generate_regions_file:
        write_regions_to_file(REGIONS)
        LOGGER.info(f'Saved Opensearch regions to file: regions.csv. Script will ignore any other inputs and exit.')
        sys.exit(0)

    if args.generate_accounts_file:
        account_pool = get_all_org_accounts(org_client)
        write_accounts_to_file(account_pool)
        LOGGER.info(f'Saved AWS Accounts in Organization to file: accounts.csv. Script will ignore any other inputs and exit.')
        sys.exit(0) 

    if args.all:
        LOGGER.info(f'Running in ORG mode for payer account: {caller_account}')
        account_pool = get_all_org_accounts(org_client)
        if args.exclude_accounts:
            LOGGER.info(f'Excluding accounts: {args.exclude_accounts}')
            exclude_accounts = [account.strip() for account in args.exclude_accounts.split(",")]
            for account in exclude_accounts:
                if account in account_pool:
                    account_pool.remove(account)
    elif args.accounts:
        if args.exclude_accounts:
            raise ValidationException('Invalid input: cannot use --exclude-accounts with --accounts argument')
        account_pool = [s.strip() for s in args.accounts.split(',')]
        all_org_accounts = get_all_org_accounts(org_client)
        validate_org_accounts(account_pool, caller_account, all_org_accounts)
        LOGGER.info(f'Running in LINKED ACCOUNT mode with accounts: {account_pool}')
    elif args.accounts_file:
        if args.exclude_accounts:
            raise ValidationException('Invalid input: cannot use --exclude-accounts with --accounts-file argument')
        account_pool = read_accounts_from_file(args.accounts_file)
        all_org_accounts = get_all_org_accounts(org_client)
        validate_org_accounts(account_pool, caller_account, all_org_accounts)
        LOGGER.info(f'Running in LINKED ACCOUNT mode with accounts: {account_pool}')
    else:
        LOGGER.info(f'Running in PAYER ACCOUNT mode for payer account: {caller_account}')
        account_pool = [caller_account]

    LOGGER.info(f'Running in specific regions: {REGIONS}')

    df = pd.DataFrame(columns=['AccountId', 'Region', 'RegionName', 
                               'DomainName', 'ARN', 'EngineVersion', 
                               'DedicatedMasterType', 'DedicatedMasterCount', 'Normalization Factor (Master Nodes)',
                               'InstanceType', 'InstanceCount', 'Normalization Factor (Data Nodes)', 
                               'WarmType', 'WarmCount', 'Normalization Factor (Ultrawarm Nodes)',
                               'CoordinatorNodeType', 'CoordinatorNodeCount', 'Normalization Factor (Coordinator Nodes)',
                               'Regional Price Per NIH', 'End of Standard Support', 'End of Extended Support', 
                               'Yearly Extended Support Cost'])
    df.to_csv(outfile, index=False)
    
    # Check if the mapping file exists, if it does, read from it
    try:
        # Try to load AOS instane mapping json file
        with open('utils/aos_instance_mapping.json', encoding="utf-8") as f:
            AOS_INSTANCE_MAPPING = json.load(f)
            LOGGER.debug(f'Read AOS instance mapping from file aos_instance_mapping.json')
    except:
        LOGGER.debug("No AOS instance mapping file found, getting mapping from AWS Pricing page")
        AOS_INSTANCE_MAPPING = get_aos_instance_mapping()

    # Check if the extended support file exists, if it does, read from it
    try:
        # Try to load AOS extended support dates json file
        with open('utils/extended_support_versions.json', encoding="utf-8") as f:
            AOS_EXTENDED_SUPPORT_VERSIONS = json.load(f)
            LOGGER.debug(f'Read AOS extended support versions mapping from file extended_support_versions.json')
    except:
        LOGGER.debug("No AOS extended support versions mapping file found, getting mapping from AWS documentation")
        AOS_EXTENDED_SUPPORT_VERSIONS = get_aos_extended_support_mapping()

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = { executor.submit(get_opensearch_extended_support_instances, account, caller_account) 
                   for account in account_pool 
                   if account not in processed_accounts }
        # Catch a thread's exceptions, if any, in the main thread
        # https://docs.python.org/3.7/library/concurrent.futures.html#concurrent.futures.as_completed
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                LOGGER.error(f"Error in processing account. Exception: {e}")
                raise


    LOGGER.info("="*25)
    LOGGER.info(f'Saved Final results to CSV file: {outfile} and deleting cached data')
    LOGGER.info("Script Execution Completed Successfully!")
    LOGGER.info("="*25)
    
    # If we have reached this point, script has been successfully executed for all accounts & regions. 
    # So, delete the .tmp_accounts_cache.json file.
    if os.path.exists('.tmp_accounts_cache.json'):
        os.remove('.tmp_accounts_cache.json')

def parse_args():
    arg_parser = argparse.ArgumentParser()
    
    group = arg_parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--accounts', help='comma separated list of AWS account IDs', type=str)
    group.add_argument('--accounts-file', help='Absolute path of the CSV file containing AWS account IDs', type=str)
    group.add_argument('--all', help="runs script for the entire AWS Organization", action='store_true')

    arg_parser.add_argument('--regions-file', help='Absolute path of the CSV file containing specific AWS regions to run the script against', type=str)
    arg_parser.add_argument('--exclude-accounts', help='comma separated list of AWS account IDs to be excluded, only applies when --all flag is used', type=str)

    arg_parser.add_argument('--generate-accounts-file', help='Creates a `accounts.csv` CSV file containing all AWS accounts in the AWS Organization', action='store_true')
    arg_parser.add_argument('--generate-regions-file', help='Creates a `regions.csv` CSV file containing all AWS regions', action='store_true')

    args = arg_parser.parse_args()
    return args

if __name__ == '__main__':
    main()