# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import requests
from bs4 import BeautifulSoup
from utils.log import get_logger
from utils.utils import read_regions_from_file
from utils.utils import ValidationException

LOGGER = get_logger('aos_mappings')

'''
This function tries to get the regions Opensearch is supported in by scraping the HTML page
from AWS Opensearch documentation. The logic relies on a specific table id in the HTML code.
However, that table id keeps changing with every (nightly) deployment/update of AWS docs.
As a result, the  below code is not used, and instead I have hardcoded the regions currently supported.
This implies we will need to manually update the regions when new ones are announced, until a more 
dynamic solution is found
'''
def get_aos_regions_2():
    LOGGER.debug("Extracting a list of AWS Regions for RDS")
    url = "https://docs.aws.amazon.com/general/latest/gr/opensearch-service.html"
    try:
        response = requests.get(url, timeout=10)    # 10 seconds
        response.raise_for_status()
    except Exception as e:
        LOGGER.error(f'Failed to get a http response from {url} to get AWS regions, script exiting...')
        raise
    soup = BeautifulSoup(response.content, "html.parser")

    #regions_section = soup.find("h3", {"id": "Concepts.RegionsAndAvailabilityZones.Availability"})
    #LOGGER.debug(f'Regions section: {regions_section}')

    #regions_section_tables = regions_section.find_all_next("table")
    #LOGGER.debug(f'Regions section tables: {regions_section_tables}')

    table = soup.find("table", {"id": "w102aac14d408b5b7"})
    #table = regions_section_tables[0]
    rows = table.find_all("tr")[1:]

    regions_map = {}
    #populate regions_map with all RDS supported regions
    for row in rows:
        cols = row.find_all("td")
        region_name = cols[0].text.strip()
        region_id = cols[1].text.strip()
        regions_map[region_id] = region_name

    LOGGER.debug(f'Regions map: {regions_map}')
    LOGGER.debug(f'Number of regions: {len(regions_map)}')
    with open('aos_regions.json', 'w', encoding="utf-8") as f:
            json.dump(regions_map, f)

    return regions_map

def get_aos_regions(regions_file_path):
    LOGGER.debug("Extracting a list of AWS Regions for Opensearch")

    regions_map = {
        "us-east-2": "US East (Ohio)", 
        "us-east-1": "US East (N. Virginia)", 
        "us-west-1": "US West (N. California)", 
        "us-west-2": "US West (Oregon)", 
        "af-south-1": "Africa (Cape Town)", 
        "ap-east-1": "Asia Pacific (Hong Kong)", 
        "ap-south-2": "Asia Pacific (Hyderabad)", 
        "ap-southeast-3": "Asia Pacific (Jakarta)", 
        "ap-southeast-5": "Asia Pacific (Malaysia)", 
        "ap-southeast-4": "Asia Pacific (Melbourne)", 
        "ap-south-1": "Asia Pacific (Mumbai)", 
        "ap-northeast-3": "Asia Pacific (Osaka)", 
        "ap-northeast-2": "Asia Pacific (Seoul)", 
        "ap-southeast-1": "Asia Pacific (Singapore)", 
        "ap-southeast-2": "Asia Pacific (Sydney)", 
        "ap-northeast-1": "Asia Pacific (Tokyo)", 
        "ca-central-1": "Canada (Central)", 
        "ca-west-1": "Canada West (Calgary)", 
        "eu-central-1": "Europe (Frankfurt)", 
        "eu-west-1": "Europe (Ireland)", 
        "eu-west-2": "Europe (London)", 
        "eu-south-1": "Europe (Milan)", 
        "eu-west-3": "Europe (Paris)", 
        "eu-south-2": "Europe (Spain)", 
        "eu-north-1": "Europe (Stockholm)", 
        "eu-central-2": "Europe (Zurich)", 
        "il-central-1": "Israel (Tel Aviv)", 
        "me-south-1": "Middle East (Bahrain)", 
        "me-central-1": "Middle East (UAE)", 
        "sa-east-1": "South America (S\u00e3o Paulo)", 
        "us-gov-east-1": "AWS GovCloud (US-East)", 
        "us-gov-west-1": "AWS GovCloud (US-West)"
    }

    if not regions_file_path:   # user has not provided a regions file
        LOGGER.debug(f'Regions map: {regions_map}')
        LOGGER.debug(f'Number of regions: {len(regions_map)}')
        return regions_map
    else:   # user has provided a regions file, read the regions from the file and validate it
        user_regions_list = read_regions_from_file(regions_file_path)

        for r in user_regions_list:
            if r not in regions_map:
                LOGGER.error("User provided regions file has invalid regions. Please fix the file, making sure you enter AWS regions ids separated by newline. Please see README for instructions on how to generate a sample Regions file")
                raise ValidationException('Invalid input: regions has invalid regions. Please fix the file & try again.')
        
        # return map with only matching entries
        regions_map = {k:v for k,v in regions_map.items() if k in user_regions_list}

        LOGGER.debug(f'Filtered Regions map: {regions_map}')
        LOGGER.debug(f'Number of regions: {len(regions_map)}')
        return regions_map   

"""
Get a mapping of AOS instance type to the Normalization Factor
For eg: m7g.medium.search = 2
"""
def get_aos_instance_mapping():
    # TODO: Fix the function to dynamically lookup NF in case there are new instance sizes added or NF values change
    # Right now its hard coded to retrun current known NF values.
    return {
        "nano":	    0.25,
        "micro":    0.5,
        "small":	1,
        "medium":	2,
        "large":	4,
        "xlarge":	8,
        "2xlarge":	16,
        "4xlarge":	32,
        "8xlarge":	64,
        "9xlarge":	72,
        "10xlarge":	80,
        "12xlarge":	96,
        "16xlarge":	128,
        "18xlarge":	144,
        "24xlarge":	192,
        "32xlarge":	256
        }

def get_aos_extended_support_mapping():
    # TODO: Fix the function to dynamically lookup AOS Extended Support versions
    #  from AWS documentation or Pricing API if supported, so that future versions can be included
    # Right now its hard coded to retrun current known extended support versions.
    return {
        "OpenSearch_1.0": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_1.1": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_1.2": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_2.3": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_2.4": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_2.5": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_2.6": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_2.7": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_2.8": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "OpenSearch_2.9": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_1.5": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_2.3": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_5.1": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_5.2": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_5.3": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_5.4": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_5.5": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_5.6": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2028-11-07"
        },
        "Elasticsearch_6.0": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_6.1": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_6.2": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_6.3": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_6.4": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_6.5": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_6.6": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_6.7": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.1": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.2": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.3": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.4": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.5": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.6": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.7": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        },
        "Elasticsearch_7.8": {
        "end_of_standard_support": "2025-11-07",
        "end_of_extended_support": "2026-11-07"
        }
    }

def get_opensearch_extended_support_cost():
    ''' Scrape the Opensearch pricing page to extract Extended Support charges
        However, this might break if the HTML code of that page changes, whihc happens frequently.
        The alternatives are:
          1/ hard code the current regional proce for extended support in a file, which will/can get outdated 
          2/ dynamically get the Opensearch Extended Support costs using teh AWS Pricing API - however,
          the Pricing API doesn't yet return extended support costs for Opensearch. 
    '''
    def get_price_map(table):
        rows = table.find_all("tr")[1:]
        price_map = {}
        for row in rows:
            cols = row.find_all("td")
            #print(cols)
            region = cols[0].text.strip()
            price_per_nih = float((cols[1].text.strip()).strip('$'))
            price_map[region] = {
                "price_per_nih": price_per_nih
            }
        return price_map
    
    LOGGER.debug("Extracting the Opensearch Extended Support pricing")
    url = "https://aws.amazon.com/opensearch-service/pricing/"
    response = requests.get(url, timeout=10)    # 10 seconds
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    extended_support_section = soup.find("h2", {"id": "Extended_support_costs"})
    LOGGER.debug(f'Extended support section: {extended_support_section}')

    extended_support_section_tables = extended_support_section.find_all_next("table")
    extended_support_price_map = get_price_map(extended_support_section_tables[0])
    LOGGER.debug(f'opensearch extended support price map: {extended_support_price_map}')
    return extended_support_price_map

"""
    Check if the given OpenSearch/Elasticsearch version falls within specified ranges,
    per https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html
    
    Args:
        opensearch_version: Version string in format "OpenSearch_X.Y" or "Elasticsearch_X.Y"
        
    Returns:
        bool: True if version is in specified ranges, False otherwise
"""
def is_extended_support_eligible(aos_version):
    try:
        engine,version = aos_version.split('_')
        major, minor = map(int, version.split('.'))
        # check if version matches any of the following: OpenSearch versions 1.0 to 1.2, OpenSearch versions 2.3 to 2.9

        if engine == 'OpenSearch':
            if major==1 and 0<=minor<=2:
                return True
            if major==2 and 3<=minor<=9:
                return True
            
        elif engine == 'Elasticsearch':
            if version in ["1.5", "2.3"]:
                return True
            if major==5 and 1<=minor<=6:
                return True
            if major==6 and 0<=minor<=7:
                return True
            if major==7 and 1<=minor<=8:
                return True
        return False
        
    except (ValueError, AttributeError):
        # Handle invalid version string format
        return False

def main():
    get_opensearch_extended_support_cost()
    get_aos_regions()

if __name__ == '__main__':
    main()